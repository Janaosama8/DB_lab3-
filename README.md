
 Group Members
- Jana Ossama – 2304044
- Takwa Abdelrahman – 2304052


In this part, we continued our website from Lab 2 using Python, Flask, and MySQL. We created a library website to manage books and authors.

The database contains two tables:

- AUTHOR:author_id, name, country
- BOOK: book_id, title, price, author_id

The author_id in the BOOK table is a foreign key that references AUTHOR.author_id. When an author is deleted, all their books are deleted automatically.

Website Features

- Register, log in, and log out.
- View books with their author IDs.
- View all authors.
- Add and edit books.
- Add and edit authors.
- Delete books.
- Delete authors and their books.
- Upload book covers and author photos.

 Requirements

- Python
- MySQL Server
- Flask
- PyMySQL
- bcrypt
- python-dotenv

 How to Run the Project
1. Create the Database

Run the SQL files from the project folder

The first file creates the database and tables. The second file inserts the test data, including at least 3 authors and 6 books.

 2. Install the Required Packages

Open the terminal inside the website folder and run:

pip install flask pymysql bcrypt python-dotenv

 3. Configure the Environment

Create an env file inside the website folder with the database connection settings:

SECRET_KEY=your_secret_key
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=registration
DB_PORT=3306

The registration database is used for user accounts, while the library database stores books and authors.
 4. Run the Website

From the website folder, run:
python lab.py
Open the website in your browser:
http://127.0.0.1:5000

Register an account or log in to access the library.
 Image Uploads
The website supports uploading book covers and author photos. Images are saved in:

static/uploads/
Supported formats are PNG, JPG, JPEG, GIF, and WEBP.

 Notes

- All registered users can access the same library.
- The SQL scripts must be run before starting the website.
- The env file contains private information and should not be uploaded to a public GitHub repository.
