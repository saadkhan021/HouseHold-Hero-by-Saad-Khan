-- 2.  Database 
CREATE DATABASE household_services;
USE household_services;

-- 3. Users Table 
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(100) UNIQUE,
    password VARCHAR(100),
    phone VARCHAR(20),
    location VARCHAR(100),     
    role VARCHAR(20),            
    cnic VARCHAR(20),
    service_type VARCHAR(50),    
    whatsapp_link VARCHAR(255),
    is_online BOOLEAN DEFAULT 1,
    rating DECIMAL(2,1) DEFAULT 0.0 -- Feature: Stars
);

CREATE TABLE reviews (
    id INT AUTO_INCREMENT PRIMARY KEY,
    seeker_id INT,
    provider_id INT,
    rating INT,
    review_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE support_tickets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    user_name VARCHAR(100),
    user_email VARCHAR(100),
    user_phone VARCHAR(20),
    issue_type VARCHAR(50),
    description TEXT,
    status VARCHAR(20) DEFAULT 'open',
    call_status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    message VARCHAR(255) NOT NULL,
    is_read INT DEFAULT 0, -- 0 matlab unread, 1 matlab read
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE bookings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    seeker_id INT NOT NULL,
    provider_id INT NOT NULL,
    booking_date DATE NOT NULL,
    booking_time VARCHAR(50) NOT NULL,
    job_description TEXT NOT NULL,
    status VARCHAR(50) DEFAULT 'pending', -- pending, accepted, completed, declined
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (seeker_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (provider_id) REFERENCES users(id) ON DELETE CASCADE
);
ALTER TABLE users ADD COLUMN profile_pic VARCHAR(255) DEFAULT 'default.png';
SELECT * FROM users WHERE role = 'provider';
SELECT * FROM users WHERE role = 'seeker';
SET SQL_SAFE_UPDATES = 0;
DELETE FROM reviews;
DELETE FROM users WHERE role = 'provider';
SET SQL_SAFE_UPDATES = 1;
USE household_services;

-- Add verification image paths and status columns
ALTER TABLE users ADD COLUMN id_photo VARCHAR(255) DEFAULT NULL;
ALTER TABLE users ADD COLUMN face_photo VARCHAR(255) DEFAULT NULL;
ALTER TABLE users ADD COLUMN verification_status VARCHAR(20) DEFAULT 'pending';
ALTER TABLE users ADD COLUMN id_verified TINYINT(1) DEFAULT 0;


ALTER TABLE users ADD COLUMN rejection_reason VARCHAR(255) DEFAULT NULL;
ALTER TABLE users ADD COLUMN latitude DECIMAL(10, 8) DEFAULT NULL;
ALTER TABLE users ADD COLUMN longitude DECIMAL(11, 8) DEFAULT NULL;