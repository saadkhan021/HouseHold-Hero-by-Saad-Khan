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

USE household_services;
CREATE TABLE reviews (
    id INT AUTO_INCREMENT PRIMARY KEY,
    seeker_id INT,
    provider_id INT,
    rating INT,
    review_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
USE household_services;
ALTER TABLE users ADD COLUMN profile_pic VARCHAR(255) DEFAULT 'default.png';
USE household_services;

SELECT * FROM users WHERE role = 'provider';

SELECT * FROM users WHERE role = 'seeker';
SET SQL_SAFE_UPDATES = 0;


DELETE FROM reviews;

DELETE FROM users WHERE role = 'provider';

SET SQL_SAFE_UPDATES = 1;