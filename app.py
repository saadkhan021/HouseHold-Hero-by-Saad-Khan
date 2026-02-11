from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
import os
from werkzeug.utils import secure_filename
# imports(Flask, render_template, etc.)

app = Flask(__name__)
app.secret_key = 'secretkey'

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

app.jinja_env.globals.update(max=max, min=min, int=int)

# --- IMAGE UPLOAD CONFIG ---
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Database Connection ---
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Saadkhan12345",  
        database="household_services"
    )

# --- ROUTES ---

# 1. LANDING PAGE (Introduction Page)
@app.route('/')
def landing():
    return render_template('landing.html')

# --- NEW PAGES ROUTES ---

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        flash("Message sent successfully! We will contact you soon. 🚀", "success")
        return redirect(url_for('contact'))
        
    return render_template('contact.html')

# 2. DASHBOARD 
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    search_query = request.args.get('q')
    
    if search_query:
        sql = "SELECT * FROM users WHERE role = 'provider' AND (service_type LIKE %s OR name LIKE %s OR location LIKE %s)"
        like_val = f"%{search_query}%"
        cursor.execute(sql, (like_val, like_val, like_val))
    else:
        cursor.execute("SELECT * FROM users WHERE role = 'provider'")
        
    providers = cursor.fetchall()
    conn.close()
    
    return render_template('index.html', providers=providers, search_query=search_query)

# 3. SIGNUP PAGE
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        phone = request.form['phone']
        location = request.form['location']
        role = request.form['role']
        service_type = request.form.get('service_type', '')
        cnic = request.form.get('cnic', '')

        # --- IMAGE UPLOAD LOGIC START ---
        profile_pic = 'default.png' 
        
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                profile_pic = filename
        # --- IMAGE UPLOAD LOGIC END ---

        clean_phone = phone.replace('+', '').replace(' ', '').replace('-', '')
        whatsapp_link = f"https://wa.me/{clean_phone}"

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            sql = "INSERT INTO users (name, email, password, phone, location, role, cnic, service_type, whatsapp_link, profile_pic) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            val = (name, email, password, phone, location, role, cnic, service_type, whatsapp_link, profile_pic)
            
            cursor.execute(sql, val)
            conn.commit()
            conn.close()
            
            flash("Account created! Please Login.", "success")
            return redirect(url_for('login')) 
        except Exception as e:
            return f"Error: {e}"
        
    return render_template('signup.html')


# 4. LOGIN PAGE (With Flash Messages)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        # Email & Password 
        cursor.execute("SELECT * FROM users WHERE email = %s AND password = %s", (email, password))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            # Session start 
            session['user_id'] = user['id']
            session['name'] = user['name']
            session['role'] = user['role']
            return redirect(url_for('dashboard'))
        else:
            # Flash Error Message
            flash("Wrong Email or Password! Please try again.", "danger")
            return redirect(url_for('login'))
            
    return render_template('login.html')

# 5. LOGOUT
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('landing'))

# --- RATING SYSTEM LOGIC ---
@app.route('/submit_rating', methods=['POST'])
def submit_rating():
    provider_id = request.form['provider_id']
    rating = int(request.form['rating'])
    seeker_id = session['user_id'] 
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        sql_insert = "INSERT INTO reviews (seeker_id, provider_id, rating) VALUES (%s, %s, %s)"
        cursor.execute(sql_insert, (seeker_id, provider_id, rating))
        conn.commit()

        cursor.execute("SELECT AVG(rating) as average FROM reviews WHERE provider_id = %s", (provider_id,))
        result = cursor.fetchone()
        
        if result and result[0]:
            new_average = round(result[0], 1) 
        else:
            new_average = rating

        cursor.execute("UPDATE users SET rating = %s WHERE id = %s", (new_average, provider_id))
        conn.commit()
        
        conn.close()
        
        flash("Rating submitted successfully! Thank you.", "success")
        
    except Exception as e:
        flash(f"Error submitting rating: {e}", "danger")
        
    return redirect(url_for('dashboard'))

# --- ADMIN STATS ROUTE ---
@app.route('/admin')
def admin_stats():
    # Security: Check if user is admin
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Providers gino
    cursor.execute("SELECT COUNT(*) FROM users WHERE role='provider'")
    provider_count = cursor.fetchone()[0]
    
    # Seekers gino
    cursor.execute("SELECT COUNT(*) FROM users WHERE role='seeker'")
    seeker_count = cursor.fetchone()[0]
    
    conn.close()
    
    return f"""
    <h1>Admin Dashboard 👑</h1>
    <h3>Total Providers: {provider_count} 🛠️</h3>
    <h3>Total Seekers: {seeker_count} 🔍</h3>
    <a href='/dashboard'>Go to Dashboard</a>
    """

# --- ENHANCED CHATBOT LOGIC ---
@app.route('/get_bot_response', methods=['POST'])
def get_bot_response():
    
    user_text = request.form['msg'].lower()
    
    # --- 1. GREETINGS  ---
    if any(word in user_text for word in ['hello', 'hi', 'salam', 'hey', 'good morning', 'good evening']):
        return "Hello! Welcome to HouseHold Hero. 👋 I can help you find Electricians, Plumbers, and more. How can I assist you?"

    # --- 2. SERVICES ENQUIRY  ---
    elif any(word in user_text for word in ['services', 'work', 'job', 'offer', 'provide']):
        return "We connect you with trusted professionals like: \n⚡ Electricians\n🔧 Plumbers\n❄️ AC Technicians\n🪑 Carpenters.\nWhich one do you need?"

    # --- 3. SPECIFIC SERVICE SEARCH ---
    elif 'electrician' in user_text or 'bijli' in user_text:
        return "Looking for an Electrician? Please search 'Electrician' in the search bar or check the dashboard for top-rated experts. ⚡"
    
    elif 'plumber' in user_text or 'nal' in user_text:
        return "Need a Plumber? You can find verified plumbers on our dashboard. Check their ratings before hiring! 🔧"
    
    elif 'ac' in user_text or 'cooling' in user_text:
        return "AC service needed? We have expert AC Technicians available. Just sign up as a Seeker to contact them. ❄️"

    # --- 4. PRICING & RATES  ---
    elif any(word in user_text for word in ['price', 'rate', 'cost', 'charges', 'fee', 'money', 'paid']):
        return "Service rates depend on the work required. You can negotiate directly with the provider on WhatsApp. We don't charge any commission! 💰"

    # --- 5. TRUST & SAFETY  ---
    elif any(word in user_text for word in ['safe', 'trust', 'verified', 'fraud', 'scam', 'guarantee']):
        return "Your safety is our priority! 🛡️ All providers have verified CNICs. Please check their 'Star Ratings' and 'Reviews' before hiring."

    # --- 6. UNRESPONSIVE PROVIDER  ---
    elif any(word in user_text for word in ['reply', 'answer', 'pick', 'busy', 'contact', 'call']):
        return "If a provider isn't replying, they might be busy. Please try contacting another 'Top Rated' provider from the list. 🕒"

    # --- 7. LOCATION QUERY  ---
    elif any(word in user_text for word in ['location', 'area', 'city', 'karachi', 'where']):
        return "We are currently active in major areas of Karachi like Gulshan, DHA, and North Nazimabad. You can see the provider's location on their card. 📍"

    # --- 8. HOW TO USE  ---
    elif any(word in user_text for word in ['how', 'use', 'register', 'signup', 'account']):
        return "It's easy! \n1️⃣ Signup as 'Seeker'.\n2️⃣ Browse Providers.\n3️⃣ Click 'Chat on WhatsApp' to hire. 🚀"

    # --- 9. GRATITUDE (Shukriya) ---
    elif any(word in user_text for word in ['thanks', 'thank', 'shukriya', 'ok', 'good']):
        return "You're welcome! Happy to help. Let us know if you need anything else. 😊"

    # --- 10. DEFAULT FALLBACK  ---
    else:
        return "I am still learning! 🤖 Please ask about 'Services', 'Rates', or 'Safety'. Or contact the provider directly via WhatsApp."
if __name__ == '__main__':
    app.run(debug=True) 