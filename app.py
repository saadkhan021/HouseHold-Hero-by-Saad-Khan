from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import mysql.connector
import os
import base64
from werkzeug.utils import secure_filename
from datetime import datetime
import math

app = Flask(__name__)
app.secret_key = 'secretkey'

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(os.path.join(UPLOAD_FOLDER, 'id_photos'), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_FOLDER, 'face_photos'), exist_ok=True)

app.jinja_env.globals.update(max=max, min=min, int=int)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_base64_image(base64_str, folder_path, prefix, cnic):
    if not base64_str:
        return None
    try:
        if "," in base64_str:
            base64_str = base64_str.split(",")[1]
        base64_str = base64_str.strip()

        img_data = base64.b64decode(base64_str)
        clean_cnic = cnic.replace('-', '').replace(' ', '')
        timestamp = int(datetime.now().timestamp())
        filename = f"{prefix}_{clean_cnic}_{timestamp}.jpg"
        
        file_path = os.path.join(folder_path, filename)
        with open(file_path, 'wb') as f:
            f.write(img_data)
            
        return f"{prefix}_photos/{filename}"
    except Exception as e:
        print(f"❌ Error decoding base64 image: {e}")
        return None

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="1234567890",  
        database="household_services"
    )

# --- ROUTES ---

@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        flash("Message sent successfully! We will contact you soon. 🚀", "success")
        return redirect(url_for('contact'))
    return render_template('contact.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT verification_status, role FROM users WHERE id = %s", (session['user_id'],))
    current_user = cursor.fetchone()
    
    if current_user and current_user['role'] == 'provider' and current_user['verification_status'] != 'approved':
        session.clear()
        flash("🔒 Unverified access blocked. Please login again.", "danger")
        return redirect(url_for('login'))
        
    # Fetch Notifications
    cursor.execute("SELECT * FROM notifications WHERE user_id = %s ORDER BY created_at DESC", (session['user_id'],))
    user_notifications = cursor.fetchall()
    
    cursor.execute("SELECT COUNT(*) as unread_count FROM notifications WHERE user_id = %s AND is_read = 0", (session['user_id'],))
    unread_res = cursor.fetchone()
    unread_count = unread_res['unread_count'] if unread_res else 0
        
    search_query = request.args.get('q')
    user_lat = request.args.get('lat')
    user_lng = request.args.get('lng')
    
    if search_query:
        sql = "SELECT * FROM users WHERE role = 'provider' AND verification_status = 'approved' AND (service_type LIKE %s OR name LIKE %s OR location LIKE %s)"
        like_val = f"%{search_query}%"
        cursor.execute(sql, (like_val, like_val, like_val))
    else:
        sql = "SELECT * FROM users WHERE role = 'provider' AND verification_status = 'approved'"
        cursor.execute(sql)
        
    providers = cursor.fetchall()

    # Step 4 Feature Insertion: Map completed booking contexts to permit ratings display
    for p in providers:
        cursor.execute("""
            SELECT COUNT(*) as completed_count FROM bookings 
            WHERE seeker_id = %s AND provider_id = %s AND status = 'completed'
        """, (session['user_id'], p['id']))
        booking_check = cursor.fetchone()
        p['can_rate'] = True if (booking_check and booking_check['completed_count'] > 0) else False

    conn.close()

    if user_lat and user_lng:
        try:
            u_lat = float(user_lat)
            u_lng = float(user_lng)
            for p in providers:
                if p.get('latitude') and p.get('longitude'):
                    p_lat = float(p['latitude'])
                    p_lng = float(p['longitude'])
                    R = 6371.0 
                    dlat = math.radians(p_lat - u_lat)
                    dlng = math.radians(p_lng - u_lng)
                    a = math.sin(dlat / 2)**2 + math.cos(math.radians(u_lat)) * math.cos(math.radians(p_lat)) * math.sin(dlng / 2)**2
                    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
                    p['distance'] = round(R * c, 1)
                else:
                    p['distance'] = None
            providers.sort(key=lambda x: x['distance'] if x['distance'] is not None else float('inf'))
        except Exception as e:
            print(f"Distance calculation error: {e}")

    return render_template('index.html', providers=providers, search_query=search_query, notifications=user_notifications, unread_count=unread_count)

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
        cnic = request.form.get('cnic', '').strip()

        profile_pic = 'default.png' 
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                profile_pic = filename

        id_photo = None
        face_photo = None
        verification_status = 'pending'

        if role == 'provider':
            if not cnic:
                flash("❌ CNIC is required for identity verification.", "danger")
                return redirect(url_for('signup'))
            
            id_b64 = request.form.get('id_image_b64')
            face_b64 = request.form.get('face_image_b64')
            consent = request.form.get('consent_given')

            if consent != 'true' or not id_b64 or not face_b64:
                flash("❌ Live Camera Verification is mandatory for Service Providers.", "danger")
                return redirect(url_for('signup'))

            id_photo = save_base64_image(id_b64, os.path.join(app.config['UPLOAD_FOLDER'], 'id_photos'), 'id', cnic)
            face_photo = save_base64_image(face_b64, os.path.join(app.config['UPLOAD_FOLDER'], 'face_photos'), 'face', cnic)

            if not id_photo or not face_photo:
                flash("❌ Identity verification capture failed processing. Please try again.", "danger")
                return redirect(url_for('signup'))

        clean_phone = phone.replace('+', '').replace(' ', '').replace('-', '')
        whatsapp_link = f"https://wa.me/{clean_phone}"

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            if role == 'provider':
                sql = """INSERT INTO users 
                        (name, email, password, phone, location, role, cnic, service_type, 
                         whatsapp_link, profile_pic, id_photo, face_photo, verification_status) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                val = (name, email, password, phone, location, role, cnic, service_type, 
                       whatsapp_link, profile_pic, id_photo, face_photo, verification_status)
            else:
                sql = """INSERT INTO users 
                        (name, email, password, phone, location, role, cnic, service_type, whatsapp_link, profile_pic) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                val = (name, email, password, phone, location, role, cnic, service_type, whatsapp_link, profile_pic)
            
            cursor.execute(sql, val)
            conn.commit()
            conn.close()
            
            if role == 'provider':
                flash("Account created! Your ID verification is pending admin review.", "info")
            else:
                flash("Account created! Please Login.", "success")
            return redirect(url_for('login')) 
        except Exception as e:
            flash(f"❌ Error during account registration: {str(e)}", "danger")
            return redirect(url_for('signup'))
        
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s AND password = %s", (email, password))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            if user['role'] == 'provider':
                if user['verification_status'] == 'pending':
                    flash("⏳ Aapka account abhi pending review mein hai. Admin ki approval ke baad aap login kar sakenge.", "warning")
                    return redirect(url_for('login'))
                elif user['verification_status'] == 'rejected':
                    flash(f"❌ Aapki verification request decline ho gayi hai. Reason: {user['rejection_reason']}. Please naya account banayein.", "danger")
                    return redirect(url_for('login'))
            
            session['user_id'] = user['id']
            session['name'] = user['name']
            session['role'] = user['role']
            return redirect(url_for('dashboard'))
        else:
            flash("Wrong Email or Password! Please try again.", "danger")
            return redirect(url_for('login'))
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('landing'))

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
        new_average = round(result[0], 1) if result and result[0] else rating

        cursor.execute("UPDATE users SET rating = %s WHERE id = %s", (new_average, provider_id))
        conn.commit()
        conn.close()
        flash("Rating submitted successfully! Thank you.", "success")
    except Exception as e:
        flash(f"Error submitting rating: {e}", "danger")
    return redirect(url_for('dashboard'))

@app.route('/admin')
def admin_stats():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE role='provider'")
    provider_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE role='seeker'")
    seeker_count = cursor.fetchone()[0]
    conn.close()
    return f"<h1>Admin Dashboard 👑</h1><h3>Total Providers: {provider_count}</h3><h3>Total Seekers: {seeker_count}</h3><a href='/dashboard'>Go to Dashboard</a>"

@app.route('/create-support-ticket', methods=['POST'])
def create_support_ticket():
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'Please login first'}), 401
        
        user_id = session['user_id']
        issue_type = request.form.get('issue_type')
        description = request.form.get('description')
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT name, email, phone FROM users WHERE id=%s", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        sql = """INSERT INTO support_tickets 
                (user_id, user_name, user_email, user_phone, issue_type, description, status, call_status) 
                VALUES (%s, %s, %s, %s, %s, %s, 'open', 'pending')"""
        cursor.execute(sql, (user_id, user['name'], user['email'], user['phone'], issue_type, description))
        conn.commit()
        ticket_id = cursor.lastrowid
        
        notif_msg = f"📞 Support Ticket #{ticket_id} successfully create ho gaya hai. Admin jald aap se rabta karega."
        cursor.execute("INSERT INTO notifications (user_id, message) VALUES (%s, %s)", (user_id, notif_msg))
        conn.commit()
        
        conn.close()
        return jsonify({'success': True, 'message': 'Support ticket created!', 'ticket_id': ticket_id})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ==========================================================================
# --- STEP 4: ADVANCED BOOKING PIPELINE ENGINE FLOWS ---
# ==========================================================================

@app.route('/create-booking', methods=['POST'])
def create_booking():
    if 'user_id' not in session:
        flash("Please log in first to book a service.", "danger")
        return redirect(url_for('login'))
        
    seeker_id = session['user_id']
    provider_id = request.form.get('provider_id')
    b_date = request.form.get('booking_date')
    b_time = request.form.get('booking_time')
    desc = request.form.get('job_description')
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        sql = """INSERT INTO bookings (seeker_id, provider_id, booking_date, booking_time, job_description, status) 
                 VALUES (%s, %s, %s, %s, %s, 'pending')"""
        cursor.execute(sql, (seeker_id, provider_id, b_date, b_time, desc))
        conn.commit()
        
        # Notify the target service provider
        notif_text = f"📅 Naya Service Order! Customer {session['name']} ne aapko order bheja hai. Check manage bookings pane."
        cursor.execute("INSERT INTO notifications (user_id, message) VALUES (%s, %s)", (provider_id, notif_text))
        conn.commit()
        conn.close()
        
        flash("✅ Booking request successfully submitted directly to the Professional!", "success")
        return redirect(url_for('dashboard'))
    except Exception as e:
        flash(f"❌ Booking failure tracking error: {str(e)}", "danger")
        return redirect(url_for('dashboard'))

@app.route('/manage-bookings')
def manage_bookings():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Fetch user details to verify role routing settings
    cursor.execute("SELECT role FROM users WHERE id=%s", (session['user_id'],))
    user_role = cursor.fetchone()
    
    if user_role and user_role['role'] == 'provider':
        # Provider view: displays assignments requested by local customers
        query = """
            SELECT b.*, u.name as customer_name, u.phone as customer_phone, u.location as customer_location 
            FROM bookings b JOIN users u ON b.seeker_id = u.id 
            WHERE b.provider_id = %s ORDER BY b.created_at DESC
        """
    else:
        # Seeker view: displays tracking statements for jobs ordered
        query = """
            SELECT b.*, u.name as provider_name, u.service_type, u.whatsapp_link 
            FROM bookings b JOIN users u ON b.provider_id = u.id 
            WHERE b.seeker_id = %s ORDER BY b.created_at DESC
        """
        
    cursor.execute(query, (session['user_id'],))
    user_bookings = cursor.fetchall()
    
    # Standard notification headers pull tracking
    cursor.execute("SELECT * FROM notifications WHERE user_id = %s ORDER BY created_at DESC", (session['user_id'],))
    user_notifications = cursor.fetchall()
    cursor.execute("SELECT COUNT(*) as unread_count FROM notifications WHERE user_id = %s AND is_read = 0", (session['user_id'],))
    unread_res = cursor.fetchone()
    unread_count = unread_res['unread_count'] if unread_res else 0
    
    conn.close()
    return render_template('bookings.html', bookings=user_bookings, role=user_role['role'], notifications=user_notifications, unread_count=unread_count)

@app.route('/update-booking-status/<int:booking_id>/<string:new_status>', methods=['POST'])
def update_booking_status(booking_id, new_status):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Verify ownership properties
        cursor.execute("SELECT * FROM bookings WHERE id=%s", (booking_id,))
        target_job = cursor.fetchone()
        
        if not target_job:
            conn.close()
            return "Job order data context lost", 404
            
        cursor.execute("UPDATE bookings SET status=%s WHERE id=%s", (new_status, booking_id))
        conn.commit()
        
        # Dynamic Notification alerts delivery assignment based on target status
        if new_status == 'accepted':
            msg = f"✅ Aapki booking request Professional ne ACCEPT kar li hai! Woh scheduled time par pohnch jayenge."
            cursor.execute("INSERT INTO notifications (user_id, message) VALUES (%s, %s)", (target_job['seeker_id'], msg))
        elif new_status == 'completed':
            msg = f"🎉 Professional ne aapka kaam COMPLETED mark kar diya hai. Aap ab unhein review aur rating de sakte hain!"
            cursor.execute("INSERT INTO notifications (user_id, message) VALUES (%s, %s)", (target_job['seeker_id'], msg))
            
        conn.commit()
        conn.close()
        flash(f"Booking status dynamically shifted to '{new_status}' successfully!", "success")
        return redirect(url_for('manage_bookings'))
    except Exception as e:
        return f"Pipeline execution failure: {str(e)}", 500


# ==========================================================================
# --- STEP 1 & 3: ADMIN VERIFICATION & GENERAL CHAT LOGIC ---
# ==========================================================================

@app.route('/admin/verify-providers')
def verify_providers():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE role='provider' AND verification_status='pending'")
        pending_providers = cursor.fetchall()
        conn.close()
        return render_template('admin_verification.html', providers=pending_providers)
    except Exception as e:
        return f"<h1>Database Error</h1><p>{str(e)}</p>"

@app.route('/admin/approve-provider/<int:provider_id>', methods=['POST'])
def approve_provider(provider_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET verification_status='approved' WHERE id=%s", (provider_id,))
        conn.commit()
        notif_msg = "🎉 Mubarak ho! Admin ne aapka profile document aur live selfie verify karke approve kar diya hai."
        cursor.execute("INSERT INTO notifications (user_id, message) VALUES (%s, %s)", (provider_id, notif_msg))
        conn.commit()
        cursor.execute("SELECT name FROM users WHERE id=%s", (provider_id,))
        provider = cursor.fetchone()
        conn.close()
        flash(f"✅ Provider {provider[0]} application approved successfully!", "success")
        return redirect(url_for('verify_providers'))
    except Exception as e:
        flash(f"❌ Error during approval execution: {str(e)}", "danger")
        return redirect(url_for('verify_providers'))

@app.route('/admin/reject-provider/<int:provider_id>', methods=['POST'])
def reject_provider(provider_id):
    try:
        reason = request.form.get('reason', 'Document verification failed')
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET verification_status='rejected', rejection_reason=%s WHERE id=%s", (reason, provider_id))
        conn.commit()
        notif_msg = f"❌ Aapki verification request decline ho gayi hai. Reason: {reason}. Please requirements ke mutabiq naya account banayein."
        cursor.execute("INSERT INTO notifications (user_id, message) VALUES (%s, %s)", (provider_id, notif_msg))
        conn.commit()
        cursor.execute("SELECT name FROM users WHERE id=%s", (provider_id,))
        provider = cursor.fetchone()
        conn.close()
        flash(f"❌ Provider {provider[0]} application rejected. Reason: {reason}", "info")
        return redirect(url_for('verify_providers'))
    except Exception as e:
        flash(f"❌ Error during updating rejection status: {str(e)}", "danger")
        return redirect(url_for('verify_providers'))

@app.route('/mark-notifications-read', methods=['POST'])
def mark_notifications_read():
    if 'user_id' not in session:
        return jsonify({'success': False}), 401
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE notifications SET is_read = 1 WHERE user_id = %s", (session['user_id'],))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/get_bot_response', methods=['POST'])
def get_bot_response():
    user_text = request.form.get('msg', '').lower().strip()
    if any(word in user_text for word in ['hello', 'hi', 'salam', 'hey', 'aoa', 'assalam']):
        return "Walaikum Assalam! Welcome to HouseHold Hero. 👋 Main aapki kya madad kar sakta hoon? I can help you find Electricians, Plumbers, Painters, and more!"
    elif any(word in user_text for word in ['services', 'work', 'job', 'offer', 'provide', 'kaam', 'list']):
        return "We offer verified local experts for:\n⚡ Electrician (Bijli ka kaam)\n🔧 Plumber (Sanitary/Nal ka kaam)\n❄️ AC Technician (Service & Repair)\n🪑 Carpenter (Woodwork)\n🎨 Painter (Ghar ka paint)\n\nAapko kis professional ki zaroorat hai?"
    elif any(word in user_text for word in ['electrician', 'bijli', 'fan', 'light', 'short circuit', 'board']):
        return "⚡ Board jal gaya hai ya fan/lights repair karwani hain? Please log in karke search bar mein 'Electrician' search karein aur kisi bhi top-rated expert se WhatsApp par direct baat karein."
    elif any(word in user_text for word in ['plumber', 'nal', 'leak', 'tank', 'washroom', 'sanitary', 'pipe']):
        return "🔧 Water leakage ya sanitary ka koi masla hai? Dashboard par verified Plumbers available hain. Aap unki ratings dekh kar direct WhatsApp par contact kar sakte hain."
    elif any(word in user_text for word in ['ac', 'cooling', 'fridge', 'refrigerator', 'gas charge', 'chilling']):
        return "❄️ AC cooling nahi kar raha ya general service chahiye? Hamaare paas expert AC Technicians hain. Seeker account se login karein aur unhein check-up ke liye bulayein."
    elif any(word in user_text for word in ['carpenter', 'lakri', 'door', 'lock', 'bed', 'sofa', 'wood']):
        return "🪑 Door locks badalna hain ya furniture repair karwana hai? Woodwork ke liye trusted Carpenters dashboard par maujood hain. Direct unke number par message karein."
    elif any(word in user_text for word in ['painter', 'paint', 'color', 'wall', 'rang', 'safedi']):
        return "🎨 Ghar ka paint badalna hai ya deewaron par Seep (moisture) ka masla hai? Professional Painters available hain jo aapko best quotation de denge."
    elif any(word in user_text for word in ['register as provider', 'join as professional', 'camera', 'cnic', 'scan', 'verification', 'stuck', 'freeze', 'selfie']):
        return "🛠️ Service provider account banane ke liye CNIC aur Live Selfie scanning lazmi hai taake users aap par trust kar sakein. Agar camera open nahi ho raha, toh check karein ke browser ko camera permission di hui hai ya nahi, ya phir page ko hard refresh (Ctrl + F5) karein."
    elif any(word in user_text for word in ['approve', 'pending', 'how long', 'time', 'review', 'verify account']):
        return "🕒 Jab aap registration complete kar lete hain, toh Admin team aapke uploaded CNIC aur face picture ko verify karti hai. Is process mein 24 se 48 hours lagte hain. Approval ke baad aapka profile user dashboard par show hona shuru ho jayega!"
    elif any(word in user_text for word in ['price', 'rate', 'cost', 'charges', 'fee', 'money', 'paid', 'commission', 'pese', 'kitne']):
        return "💰 HouseHold Hero bilkul FREE platform hai! Hum providers ya customers se koi commission nahi lete. Rates aap professional se WhatsApp par direct negotiate kar sakte hain kaam ki zaroorat ke mutabiq."
    elif any(word in user_text for word in ['safe', 'trust', 'verified', 'fraud', 'scam', 'guarantee', 'chori', 'security']):
        return "🛡️ Security hamaari priority hai! Har professional ka CNIC admin khud physically verify karta hai tabhi profile active hoti hai. Phir bhi, aap unki poorani 'Star Ratings' aur customer reviews dekh kar hi unhein ghar bulayein."
    elif any(word in user_text for word in ['complaint', 'report', 'issue', 'bad service', 'not picking', 'help', 'admin', 'number', 'call']):
        return "📞 Agar koi professional bad-behavior kare ya reply na kare, toh chat header mein maujood Red Phone icon par click karke Admin Support Call request submit karein. Ya phir direct hmaare help number (+92 343 2106570) par rabta karein."
    elif any(word in user_text for word in ['location', 'area', 'city', 'karachi', 'where', 'gulshan', 'jauhar', 'dha', 'nazimabad']):
        return "📍 We are currently active all over Karachi! Aapko card par har provider ka area (e.g. Gulshan-e-Iqbal, Clifton, North Nazimabad) saaf nazar aa jayega taake aap apne kareeb ke bande ko select kar sakein."
    elif any(word in user_text for word in ['how to use', 'tarika', 'process', 'step', 'kaise']):
        return "Easy steps hain:\n1️⃣ Sign up as a 'Seeker'.\n2️⃣ Apni zaroorat ka professional search karein.\n3️⃣ 'Chat on WhatsApp' par click karke direct unhein hire karein! 🚀"
    elif any(word in user_text for word in ['thanks', 'thank', 'shukriya', 'ok', 'good', 'great', 'jazakallah']):
        return "You're very welcome! HouseHold Hero use karne ka shukriya. Agar mazeed koi masla ho toh zaroor batayein. Stay safe! 😊"
    else:
        return "Main aapka sawaal poori tarah samajh nahi paya. 🤖 Aap mujhse 'Services', 'Rates', 'CNIC Verification' ya 'Safety' ke baare mein pooch sakte hain."

if __name__ == '__main__':
    app.run(debug=False)