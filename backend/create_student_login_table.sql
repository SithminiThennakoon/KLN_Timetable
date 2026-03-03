CREATE TABLE IF NOT EXISTS student_login (
    stu_id VARCHAR(12) PRIMARY KEY,
    studentemail VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    CONSTRAINT chk_stu_id_format
        CHECK (stu_id REGEXP '^[A-Za-z]{2,3}/[0-9]{4}/[0-9]{3}$')
);
