-- Create database if it doesn't exist
CREATE DATABASE IF NOT EXISTS kln_timetable;
USE kln_timetable;

-- Create semester table
CREATE TABLE IF NOT EXISTS semester (
    Semester_ID INT AUTO_INCREMENT PRIMARY KEY,
    Semester_name VARCHAR(50) NOT NULL,
    Academic_year VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Create group table (Batches)
CREATE TABLE IF NOT EXISTS `group` (
    Group_ID INT AUTO_INCREMENT PRIMARY KEY,
    Group_name VARCHAR(100) NOT NULL,
    Semester_Semester_ID INT NOT NULL,
    Student_count INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (Semester_Semester_ID) REFERENCES semester(Semester_ID) ON DELETE CASCADE
);

-- Create time_table table
CREATE TABLE IF NOT EXISTS time_table (
    timetable_ID INT AUTO_INCREMENT PRIMARY KEY,
    version VARCHAR(50),
    Day VARCHAR(20),
    Lecturer_ID INT,
    Group_Group_ID INT NOT NULL,
    Room_ID INT,
    TimeSlot_ID INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (Group_Group_ID) REFERENCES `group`(Group_ID) ON DELETE CASCADE
);

-- Insert sample semesters
INSERT INTO semester (Semester_name, Academic_year) VALUES
('Semester 1', '2024/2025'),
('Semester 2', '2024/2025');

-- Show created tables
SHOW TABLES;
