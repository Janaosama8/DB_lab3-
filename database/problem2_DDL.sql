

CREATE DATABASE IF NOT EXISTS library;
USE library;

CREATE TABLE IF NOT EXISTS publisher (
    publisher_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    country VARCHAR(50)
);
CREATE TABLE IF NOT EXISTS category (
    category_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL
);


CREATE TABLE IF NOT EXISTS member (
    member_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL,
    join_date DATE
);

ALTER TABLE book
ADD COLUMN publish_year INT,
ADD COLUMN publisher_id INT,
ADD COLUMN category_id INT;

ALTER TABLE book
ADD CONSTRAINT fk_book_publisher
FOREIGN KEY (publisher_id)
REFERENCES publisher(publisher_id);

ALTER TABLE book
ADD CONSTRAINT fk_book_category
FOREIGN KEY (category_id)
REFERENCES category(category_id);

CREATE TABLE IF NOT EXISTS loan (
    loan_id INT PRIMARY KEY AUTO_INCREMENT,
    book_id INT NOT NULL,
    member_id INT NOT NULL,
    loan_date DATE NOT NULL,
    return_date DATE NULL,
    FOREIGN KEY (book_id)
        REFERENCES book(book_id)
        ON DELETE CASCADE,
    FOREIGN KEY (member_id)
        REFERENCES member(member_id)
);
