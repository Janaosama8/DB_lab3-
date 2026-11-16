
USE library;

SELECT
    b.book_id,
    b.title,
    b.price,
    a.name AS author,
    p.name AS publisher,
    c.name AS category
FROM book b
JOIN author a ON b.author_id = a.author_id
JOIN publisher p ON b.publisher_id = p.publisher_id
JOIN category c ON b.category_id = c.category_id
ORDER BY b.book_id;


SELECT
    a.name,
    COUNT(b.book_id) AS number_of_books
FROM author a
LEFT JOIN book b ON a.author_id = b.author_id
GROUP BY a.author_id, a.name
ORDER BY a.name;


SELECT
    b.title AS book_title,
    m.name AS member_name,
    l.loan_date
FROM loan l
JOIN book b ON l.book_id = b.book_id
JOIN member m ON l.member_id = m.member_id
WHERE l.return_date IS NULL
ORDER BY l.loan_date;



SELECT
    m.member_id,
    m.name
FROM member m
LEFT JOIN loan l
    ON m.member_id = l.member_id
WHERE l.loan_id IS NULL;



SELECT
    b.book_id,
    b.title
FROM book b
LEFT JOIN loan l
    ON b.book_id = l.book_id
WHERE l.loan_id IS NULL;



SELECT
    b.title,
    COUNT(l.loan_id) AS number_of_loans
FROM book b
JOIN loan l ON b.book_id = l.book_id
GROUP BY b.book_id, b.title
ORDER BY number_of_loans DESC, b.book_id ASC
LIMIT 3;



SELECT
    m.name,
    COUNT(l.loan_id) AS number_of_loans
FROM member m
JOIN loan l ON m.member_id = l.member_id
GROUP BY m.member_id, m.name
ORDER BY number_of_loans DESC
LIMIT 1;


SELECT
    b.title,
    a.name AS author_name,
    p.name AS publisher_name,
    a.country
FROM book b
JOIN author a ON b.author_id = a.author_id
JOIN publisher p ON b.publisher_id = p.publisher_id
WHERE a.country = p.country
ORDER BY b.title;
