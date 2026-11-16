
import os
import re
import uuid
import pymysql
import bcrypt

from flask import Flask, request, redirect, session
from markupsafe import escape
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

load_dotenv("env")

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

if not app.secret_key:
    raise RuntimeError("SECRET_KEY is missing from env file")

UPLOAD_FOLDER = os.path.join(app.root_path, "static", "uploads")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_image(file):
    if not file or not file.filename:
        return None
    if not allowed_file(file.filename):
        raise ValueError("Allowed image types: PNG, JPG, JPEG, GIF, WEBP")

    filename = secure_filename(file.filename)
    unique_name = f"{uuid.uuid4().hex}_{filename}"
    file.save(os.path.join(app.config["UPLOAD_FOLDER"], unique_name))
    return unique_name


def get_db(database=None):
    return pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD"),
        database=database or os.getenv("DB_NAME", "registration"),
        port=int(os.getenv("DB_PORT", "3306")),
        cursorclass=pymysql.cursors.DictCursor
    )


def get_library_db():
    return get_db("library")


def page(title, content):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{escape(title)}</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: Arial; background: #f2f4f7; padding: 20px; }}
            .box {{ max-width: 1000px; margin: auto; background: white;
                    padding: 20px; border-radius: 8px; overflow-x: auto; }}
            input, select, button {{ padding: 10px; border: 1px solid #ddd;
                    border-radius: 5px; box-sizing: border-box; margin-top: 5px; }}
            button {{ cursor: pointer; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ padding: 10px; text-align: left; border: 1px solid #ddd; }}
            th {{ background: #eef2f7; }}
            .cover {{ width: 100px; height: 130px; object-fit: contain; }}
            .photo {{ width: 100px; height: 100px; object-fit: cover; border-radius: 50%; }}
            .error {{ color: red; }}
            .nav {{ margin-bottom: 20px; }}
        </style>
    </head>
    <body><div class="box">{content}</div></body>
    </html>
    """


def error_page(message, back="/"):
    return page("Error", f'<p class="error">{escape(message)}</p><a href="{escape(back)}">Go back</a>')


def valid_email(email):
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email))




def login_form():
    return page("Login", """
        <h2>Login</h2>
        <form method="POST" action="/login">
            <p>Email<br><input type="email" name="email" required></p>
            <p>Password<br><input type="password" name="password" required></p>
            <button type="submit">Login</button>
        </form>
        <a href="/register">Register</a>
    """)


def register_form(message=""):
    return page("Register", f"""
        <h2>Register</h2>
        <p class="error">{escape(message)}</p>
        <form method="POST" action="/register">
            <p>Name<br><input name="name" maxlength="100" required></p>
            <p>Email<br><input type="email" name="email" required></p>
            <p>Password<br><input type="password" name="password" minlength="8" required></p>
            <p>Confirm Password<br><input type="password" name="confirm" minlength="8" required></p>
            <button type="submit">Register</button>
        </form>
        <a href="/">Login</a>
    """)


@app.route("/")
def home():
    if "user_id" not in session:
        return login_form()

    content = f"""
        <h2>Welcome, {escape(session["name"])}!</h2>
        <h3>Library Management System</h3>

        <hr>

        <p><a href="/books">View Books</a></p>
        <p><a href="/authors">View Authors</a></p>
        

        <hr>

        <a href="/logout">Logout</a>
    """

    return page("Dashboard", content)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return register_form(session.pop("register_message", ""))

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    confirm = request.form.get("confirm", "")

    if not name or not email or not password or not confirm:
        session["register_message"] = "All fields are required"
        return redirect("/register")

    if len(name) > 100:
        session["register_message"] = "Name is too long"
        return redirect("/register")

    if not valid_email(email):
        session["register_message"] = "Enter a valid email"
        return redirect("/register")

    if len(password) < 8:
        session["register_message"] = "Password must be at least 8 characters"
        return redirect("/register")

    if password != confirm:
        session["register_message"] = "Passwords do not match"
        return redirect("/register")

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    db = get_db()

    try:
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (%s, %s, %s)",
                (name, email, hashed)
            )
        db.commit()
    except pymysql.err.IntegrityError:
        session["register_message"] = "Email already exists"
        return redirect("/register")
    finally:
        db.close()

    return redirect("/")


@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    if not email or not password:
        return error_page("Email and password are required")

    if not valid_email(email):
        return error_page("Enter a valid email")

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT user_id, name, password_hash FROM users WHERE email=%s",
                (email,)
            )
            user = cur.fetchone()
    finally:
        db.close()

    if not user or not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
        return error_page("Invalid email or password")

    session.clear()
    session["user_id"] = user["user_id"]
    session["name"] = user["name"]
    return redirect("/")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/books")
def books():
    conn = get_library_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM book ORDER BY book_id")
            books_list = cursor.fetchall()

        content = """
        <h2>Library Books</h2>
       <div class="nav">
    <a href="/search_books">Search Books</a> |
    <a href="/authors">View Authors</a> |
    <a href="/add_book">Add Book</a> |
    <a href="/catalogue">Catalogue</a> |
    <a href="/reports">Reports</a> |
    <a href="/loans_reports">Loans Reports</a> |
    <a href="/most_borrowed">Most Borrowed</a> |
    <a href="/authors_books">Authors and Books</a> |
    <a href="/add_author">Add Author</a> |
    <a href="/logout">Logout</a>
        </div>
        <table><tr><th>ID</th><th>Cover</th><th>Title</th>
        <th>Price</th><th>Author ID</th><th>Actions</th></tr>
        """

        for book in books_list:
            bid = book["book_id"]
            cover = ""
            if book.get("cover_image"):
                cover = f'<img class="cover" src="/static/uploads/{escape(book["cover_image"])}" alt="Book cover">'

            content += f"""
            <tr>
                <td>{bid}</td><td>{cover}</td>
                <td>{escape(book["title"])}</td>
                <td>{escape(str(book["price"]))}</td>
                <td>{book["author_id"]}</td>
                <td>
                    <a href="/edit_book/{bid}">Edit</a>
                    <form method="POST" action="/delete_book/{bid}"
                    onsubmit="return confirm('Delete this book?')">
                    <button type="submit">Remove</button></form>
                </td>
            </tr>
            """

        return page("Library Books", content + "</table>")
    finally:
        conn.close()

@app.route("/catalogue")
def catalogue():
    conn = get_library_db()

    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT
                    b.title,
                    a.name AS author_name,
                    p.name AS publisher_name,
                    c.name AS category_name
                FROM book b
                LEFT JOIN author a
                    ON b.author_id = a.author_id
                LEFT JOIN publisher p
                    ON b.publisher_id = p.publisher_id
                LEFT JOIN category c
                    ON b.category_id = c.category_id
                ORDER BY b.title
            """)

            books_list = cursor.fetchall()

        content = """
        <h2>Catalogue</h2>

        <table>
            <tr>
                <th>Book Title</th>
                <th>Author Name</th>
                <th>Publisher Name</th>
                <th>Category Name</th>
            </tr>
        """

        for book in books_list:
            content += f"""
            <tr>
                <td>{escape(book["title"])}</td>
                <td>{escape(book["author_name"] or "")}</td>
                <td>{escape(book["publisher_name"] or "")}</td>
                <td>{escape(book["category_name"] or "")}</td>
            </tr>
            """

        content += """
        </table>
        <br>
        <a href="/books">Back to Books</a>
        """

        return page("Catalogue", content)

    finally:
        conn.close()

@app.route("/reports")
def reports():
    conn = get_library_db()

    try:
        with conn.cursor() as cursor:

            # Report A: Number of books and average price per category
            cursor.execute("""
                SELECT
                    c.name AS category_name,
                    COUNT(b.book_id) AS number_of_books,
                    AVG(b.price) AS average_price
                FROM category c
                LEFT JOIN book b
                    ON c.category_id = b.category_id
                GROUP BY c.category_id, c.name
                ORDER BY c.name
            """)
            category_report = cursor.fetchall()

            # Report B: Authors who wrote at least 2 books
            cursor.execute("""
                SELECT
                    a.name AS author_name,
                    COUNT(b.book_id) AS number_of_books
                FROM author a
                JOIN book b
                    ON a.author_id = b.author_id
                GROUP BY a.author_id, a.name
                HAVING COUNT(b.book_id) >= 2
                ORDER BY a.name
            """)
            author_report = cursor.fetchall()

            # Report C: Total, smallest and largest book price
            cursor.execute("""
                SELECT
                    SUM(price) AS total_price,
                    MIN(price) AS smallest_price,
                    MAX(price) AS largest_price
                FROM book
            """)
            price_report = cursor.fetchone()

        content = """
        <h2>Library Reports</h2>

        <h3>A. Books and Average Price per Category</h3>

        <table>
            <tr>
                <th>Category</th>
                <th>Number of Books</th>
                <th>Average Price</th>
            </tr>
        """

        for row in category_report:
            average = row["average_price"]
            average = f"{average:.2f}" if average is not None else "N/A"

            content += f"""
            <tr>
                <td>{escape(row["category_name"])}</td>
                <td>{row["number_of_books"]}</td>
                <td>{average}</td>
            </tr>
            """

        content += """
        </table>

        <h3>B. Authors Who Wrote at Least 2 Books</h3>

        <table>
            <tr>
                <th>Author Name</th>
                <th>Number of Books</th>
            </tr>
        """

        for row in author_report:
            content += f"""
            <tr>
                <td>{escape(row["author_name"])}</td>
                <td>{row["number_of_books"]}</td>
            </tr>
            """

        content += f"""
        </table>

        <h3>C. Library Price Summary</h3>

        <table>
            <tr>
                <th>Total Price</th>
                <th>Smallest Price</th>
                <th>Largest Price</th>
            </tr>
            <tr>
                <td>{price_report["total_price"] or 0}</td>
                <td>{price_report["smallest_price"] or 0}</td>
                <td>{price_report["largest_price"] or 0}</td>
            </tr>
        </table>

        <br>
        <a href="/books">Back to Books</a>
        """

        return page("Library Reports", content)

    finally:
        conn.close()


@app.route("/loans_reports")
def loans_reports():
    conn = get_library_db()

    try:
        with conn.cursor() as cursor:

            # A. Loans not returned yet
            cursor.execute("""
                SELECT
                    b.title AS book_title,
                    m.name AS member_name,
                    l.loan_date
                FROM loan l
                JOIN book b ON l.book_id = b.book_id
                JOIN member m ON l.member_id = m.member_id
                WHERE l.return_date IS NULL
                ORDER BY l.loan_date
            """)
            unreturned_loans = cursor.fetchall()

            # B. Members who never borrowed a book
            cursor.execute("""
                SELECT m.member_id, m.name
                FROM member m
                LEFT JOIN loan l ON m.member_id = l.member_id
                WHERE l.loan_id IS NULL
                ORDER BY m.name
            """)
            members_without_loans = cursor.fetchall()

            # C. Books that were never borrowed
            cursor.execute("""
                SELECT b.book_id, b.title
                FROM book b
                LEFT JOIN loan l ON b.book_id = l.book_id
                WHERE l.loan_id IS NULL
                ORDER BY b.title
            """)
            books_without_loans = cursor.fetchall()

        content = """
        <h2>Loans Reports</h2>

        <h3>A. Loans Not Returned Yet</h3>
        <table>
            <tr>
                <th>Book Title</th>
                <th>Member Name</th>
                <th>Loan Date</th>
            </tr>
        """

        for row in unreturned_loans:
            content += f"""
            <tr>
                <td>{escape(row["book_title"])}</td>
                <td>{escape(row["member_name"])}</td>
                <td>{row["loan_date"]}</td>
            </tr>
            """

        content += """
        </table>

        <h3>B. Members Who Never Borrowed a Book</h3>
        <table>
            <tr>
                <th>Member ID</th>
                <th>Member Name</th>
            </tr>
        """

        for row in members_without_loans:
            content += f"""
            <tr>
                <td>{row["member_id"]}</td>
                <td>{escape(row["name"])}</td>
            </tr>
            """

        content += """
        </table>

        <h3>C. Books That Were Never Borrowed</h3>
        <table>
            <tr>
                <th>Book ID</th>
                <th>Book Title</th>
            </tr>
        """

        for row in books_without_loans:
            content += f"""
            <tr>
                <td>{row["book_id"]}</td>
                <td>{escape(row["title"])}</td>
            </tr>
            """

        content += """
        </table>
        <br>
        <a href="/books">Back to Books</a>
        """

        return page("Loans Reports", content)

    finally:
        conn.close()

@app.route("/most_borrowed")
def most_borrowed():
    conn = get_library_db()

    try:
        with conn.cursor() as cursor:

            # A. The 3 books with the most loans
            cursor.execute("""
                SELECT
                    b.title AS book_title,
                    COUNT(l.loan_id) AS number_of_loans
                FROM book b
                JOIN loan l
                    ON b.book_id = l.book_id
                GROUP BY b.book_id, b.title
                ORDER BY number_of_loans DESC
                LIMIT 3
            """)
            top_books = cursor.fetchall()

            # B. The member with the most loans
            cursor.execute("""
                SELECT
                    m.name AS member_name,
                    COUNT(l.loan_id) AS number_of_loans
                FROM member m
                JOIN loan l
                    ON m.member_id = l.member_id
                GROUP BY m.member_id, m.name
                ORDER BY number_of_loans DESC
                LIMIT 1
            """)
            top_member = cursor.fetchall()

        content = """
        <h2>Most Borrowed Report</h2>

        <h3>Top 3 Most Borrowed Books</h3>
        <table>
            <tr>
                <th>Book Title</th>
                <th>Number of Loans</th>
            </tr>
        """

        for book in top_books:
            content += f"""
            <tr>
                <td>{escape(book["book_title"])}</td>
                <td>{book["number_of_loans"]}</td>
            </tr>
            """

        content += """
        </table>

        <h3>Member with the Most Loans</h3>
        <table>
            <tr>
                <th>Member Name</th>
                <th>Number of Loans</th>
            </tr>
        """

        for member in top_member:
            content += f"""
            <tr>
                <td>{escape(member["member_name"])}</td>
                <td>{member["number_of_loans"]}</td>
            </tr>
            """

        content += """
        </table>
        <br>
        <a href="/books">Back to Books</a>
        """

        return page("Most Borrowed Report", content)

    finally:
        conn.close()

@app.route("/authors_books")
def authors_books():
    conn = get_library_db()

    try:
        with conn.cursor() as cursor:

            # A. Every author and number of books
            cursor.execute("""
                SELECT
                    a.name AS author_name,
                    COUNT(b.book_id) AS number_of_books
                FROM author a
                LEFT JOIN book b
                    ON a.author_id = b.author_id
                GROUP BY a.author_id, a.name
                ORDER BY a.name
            """)
            authors_report = cursor.fetchall()

            # B. Books whose author and publisher
            # come from the same country
            cursor.execute("""
                SELECT
                    b.title AS book_title,
                    a.name AS author_name,
                    p.name AS publisher_name,
                    a.country AS country
                FROM book b
                JOIN author a
                    ON b.author_id = a.author_id
                JOIN publisher p
                    ON b.publisher_id = p.publisher_id
                WHERE a.country = p.country
                ORDER BY b.title
            """)
            same_country_books = cursor.fetchall()

        content = """
        <h2>Authors and Books Report</h2>

        <h3>Every Author and Number of Books</h3>
        <table>
            <tr>
                <th>Author Name</th>
                <th>Number of Books</th>
            </tr>
        """

        for author in authors_report:
            content += f"""
            <tr>
                <td>{escape(author["author_name"])}</td>
                <td>{author["number_of_books"]}</td>
            </tr>
            """

        content += """
        </table>

        <h3>Books with Author and Publisher from Same Country</h3>
        <table>
            <tr>
                <th>Book Title</th>
                <th>Author Name</th>
                <th>Publisher Name</th>
                <th>Country</th>
            </tr>
        """

        for book in same_country_books:
            content += f"""
            <tr>
                <td>{escape(book["book_title"])}</td>
                <td>{escape(book["author_name"])}</td>
                <td>{escape(book["publisher_name"])}</td>
                <td>{escape(book["country"] or "")}</td>
            </tr>
            """

        content += """
        </table>
        <br>
        <a href="/books">Back to Books</a>
        """

        return page("Authors and Books Report", content)

    finally:
        conn.close()

@app.route("/add_book", methods=["GET", "POST"])
def add_book():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        price = request.form.get("price", "").strip()
        author_id = request.form.get("author_id", "")

        if not title or len(title) > 100 or not price or not author_id:
            return error_page("Please complete all required fields", "/add_book")

        try:
            price = float(price)
            author_id = int(author_id)
            if price < 0:
                raise ValueError("Price cannot be negative")
            cover = save_image(request.files.get("cover_image"))
        except ValueError as e:
            return error_page(str(e) or "Invalid price or author", "/add_book")

        conn = get_library_db()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO book (title, price, author_id, cover_image) VALUES (%s, %s, %s, %s)",
                    (title, price, author_id, cover)
                )
            conn.commit()
        except pymysql.err.IntegrityError:
            return error_page("Please select a valid author", "/add_book")
        finally:
            conn.close()

        return redirect("/books")

    conn = get_library_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM author ORDER BY name")
            authors_list = cursor.fetchall()

        content = "<h2>Add a Book</h2>"
        if not authors_list:
            content += "<p>Add an author before adding a book.</p>"
        else:
            content += """
            <form method="POST" enctype="multipart/form-data">
                Title:<br><input name="title" maxlength="100" required><br><br>
                Price:<br><input type="number" name="price" step="0.01" min="0" required><br><br>
                Author:<br><select name="author_id" required>
            """
            for author in authors_list:
                content += f'<option value="{author["author_id"]}">{escape(author["name"])}</option>'

            content += """
                </select><br><br>
                Book Cover:<br><input type="file" name="cover_image" accept=".png,.jpg,.jpeg,.gif,.webp,image/*"><br><br>
                <button type="submit">Add Book</button>
            </form>
            """

        return page("Add Book", content + '<br><a href="/books">Back to Books</a>')
    finally:
        conn.close()


@app.route("/edit_book/<int:book_id>", methods=["GET", "POST"])
def edit_book(book_id):
    conn = get_library_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM book WHERE book_id=%s", (book_id,))
            book = cursor.fetchone()
            if not book:
                return "Book not found", 404

            cursor.execute("SELECT * FROM author ORDER BY name")
            authors_list = cursor.fetchall()

            if request.method == "POST":
                title = request.form.get("title", "").strip()
                price = request.form.get("price", "").strip()
                author_id = request.form.get("author_id", "")

                if not title or len(title) > 100 or not price or not author_id:
                    return error_page("Enter a title, price and author", f"/edit_book/{book_id}")

                try:
                    price = float(price)
                    author_id = int(author_id)
                    if price < 0:
                        raise ValueError("Price cannot be negative")
                    new_cover = save_image(request.files.get("cover_image"))
                except ValueError as e:
                    return error_page(str(e) or "Invalid price or author", f"/edit_book/{book_id}")

                cover = new_cover or book.get("cover_image")
                cursor.execute(
                    "UPDATE book SET title=%s, price=%s, author_id=%s, cover_image=%s WHERE book_id=%s",
                    (title, price, author_id, cover, book_id)
                )
                conn.commit()
                return redirect("/books")

        cover = ""
        if book.get("cover_image"):
            cover = f'<img class="cover" src="/static/uploads/{escape(book["cover_image"])}" alt="Current cover">'

        content = f"""
        <h2>Edit Book</h2>{cover}
        <form method="POST" enctype="multipart/form-data">
            Title:<br><input name="title" maxlength="100" value="{escape(book["title"])}" required><br><br>
            Price:<br><input type="number" name="price" step="0.01" min="0" value="{escape(str(book["price"]))}" required><br><br>
            Author:<br><select name="author_id" required>
        """
        for author in authors_list:
            selected = "selected" if author["author_id"] == book["author_id"] else ""
            content += f'<option value="{author["author_id"]}" {selected}>{escape(author["name"])}</option>'

        content += """
            </select><br><br>
            New Book Cover (optional):<br>
            <input type="file" name="cover_image" accept=".png,.jpg,.jpeg,.gif,.webp,image/*"><br><br>
            <button type="submit">Save Changes</button>
        </form><br><a href="/books">Back to Books</a>
        """
        return page("Edit Book", content)
    finally:
        conn.close()


@app.route("/delete_book/<int:book_id>", methods=["POST"])
def delete_book(book_id):
    conn = get_library_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM book WHERE book_id=%s", (book_id,))
        conn.commit()
    finally:
        conn.close()
    return redirect("/books")


@app.route("/authors")
def authors():
    conn = get_library_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM author ORDER BY author_id")
            authors_list = cursor.fetchall()

        content = """
        <h2>Library Authors</h2>
        <div class="nav">
            <a href="/books">View Books</a> |
            <a href="/add_author">Add Author</a> |
            <a href="/logout">Logout</a>
        </div>
        <table><tr><th>ID</th><th>Photo</th><th>Name</th>
        <th>Country</th><th>Actions</th></tr>
        """

        for author in authors_list:
            aid = author["author_id"]
            photo = ""
            if author.get("photo"):
                photo = f'<img class="photo" src="/static/uploads/{escape(author["photo"])}" alt="Author photo">'

            content += f"""
            <tr>
                <td>{aid}</td><td>{photo}</td>
                <td>{escape(author["name"])}</td>
                <td>{escape(author["country"] or "")}</td>
                <td>
                    <a href="/edit_author/{aid}">Edit</a>
                    <form method="POST" action="/delete_author/{aid}"
                    onsubmit="return confirm('Delete this author and their books?')">
                    <button type="submit">Remove</button></form>
                </td>
            </tr>
            """

        return page("Library Authors", content + "</table>")
    finally:
        conn.close()


@app.route("/add_author", methods=["GET", "POST"])
def add_author():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        country = request.form.get("country", "").strip()

        if not name or len(name) > 100 or len(country) > 50:
            return error_page("Enter a name up to 100 characters and country up to 50 characters", "/add_author")

        try:
            photo = save_image(request.files.get("photo"))
        except ValueError as e:
            return error_page(str(e), "/add_author")

        conn = get_library_db()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO author (name, country, photo) VALUES (%s, %s, %s)",
                    (name, country or None, photo)
                )
            conn.commit()
        finally:
            conn.close()

        return redirect("/authors")

    content = """
    <h2>Add an Author</h2>
    <form method="POST" enctype="multipart/form-data">
        Name:<br><input name="name" maxlength="100" required><br><br>
        Country:<br><input name="country" maxlength="50"><br><br>
        Author Photo:<br><input type="file" name="photo" accept=".png,.jpg,.jpeg,.gif,.webp,image/*"><br><br>
        <button type="submit">Add Author</button>
    </form>
    <br><a href="/authors">Back to Authors</a>
    """
    return page("Add Author", content)


@app.route("/edit_author/<int:author_id>", methods=["GET", "POST"])
def edit_author(author_id):
    conn = get_library_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM author WHERE author_id=%s", (author_id,))
            author = cursor.fetchone()
            if not author:
                return "Author not found", 404

            if request.method == "POST":
                name = request.form.get("name", "").strip()
                country = request.form.get("country", "").strip()

                if not name or len(name) > 100 or len(country) > 50:
                    return error_page("Enter a valid name and country", f"/edit_author/{author_id}")

                try:
                    new_photo = save_image(request.files.get("photo"))
                except ValueError as e:
                    return error_page(str(e), f"/edit_author/{author_id}")

                photo = new_photo or author.get("photo")
                cursor.execute(
                    "UPDATE author SET name=%s, country=%s, photo=%s WHERE author_id=%s",
                    (name, country or None, photo, author_id)
                )
                conn.commit()
                return redirect("/authors")

        photo = ""
        if author.get("photo"):
            photo = f'<img class="photo" src="/static/uploads/{escape(author["photo"])}" alt="Current author photo">'

        content = f"""
        <h2>Edit Author</h2>{photo}
        <form method="POST" enctype="multipart/form-data">
            Name:<br><input name="name" maxlength="100" value="{escape(author["name"])}" required><br><br>
            Country:<br><input name="country" maxlength="50" value="{escape(author["country"] or "")}"><br><br>
            New Author Photo (optional):<br>
            <input type="file" name="photo" accept=".png,.jpg,.jpeg,.gif,.webp,image/*"><br><br>
            <button type="submit">Save Changes</button>
        </form><br><a href="/authors">Back to Authors</a>
        """
        return page("Edit Author", content)
    finally:
        conn.close()


@app.route("/delete_author/<int:author_id>", methods=["POST"])
def delete_author(author_id):
    conn = get_library_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM author WHERE author_id=%s", (author_id,))
        conn.commit()
    finally:
        conn.close()
    return redirect("/authors")


@app.route("/search_books")
def search_books():

    title = request.args.get("title", "").strip()
    min_price = request.args.get("min_price", "").strip()
    max_price = request.args.get("max_price", "").strip()
    category_id = request.args.get("category_id", "").strip()

    conn = get_library_db()

    try:
        with conn.cursor() as cursor:

            # Get all categories for the dropdown
            cursor.execute("SELECT * FROM category ORDER BY name")
            categories = cursor.fetchall()

            query = """
                SELECT b.book_id, b.title, b.price,
                       a.name AS author_name,
                       c.name AS category_name
                FROM book b
                LEFT JOIN author a ON b.author_id = a.author_id
                LEFT JOIN category c ON b.category_id = c.category_id
                WHERE 1=1
            """

            values = []
            if title:
                query += " AND b.title LIKE %s"
                values.append("%" + title + "%")

           
            if min_price or max_price:
                if not min_price or not max_price:
                    return error_page(
                        "Enter both minimum and maximum prices",
                        "/search_books"
                    )

                try:
                    minimum = float(min_price)
                    maximum = float(max_price)

                    if minimum < 0 or maximum < minimum:
                        return error_page("Invalid price range", "/search_books")

                except ValueError:
                    return error_page("Enter valid prices", "/search_books")

                query += " AND b.price BETWEEN %s AND %s"
                values.extend([minimum, maximum])


            if category_id:
                try:
                    category_id = int(category_id)
                except ValueError:
                    return error_page("Invalid category", "/search_books")

                query += " AND b.category_id = %s"
                values.append(category_id)

         
            query += " ORDER BY b.price ASC"

            cursor.execute(query, values)
            results = cursor.fetchall()

        content = """
            <h2>Search Books</h2>

            <form method="GET">
                Title:
                <input name="title" placeholder="Enter book title">

                <br><br>

                Minimum Price:
                <input type="number" name="min_price" step="0.01" min="0">

                <br><br>

                Maximum Price:
                <input type="number" name="max_price" step="0.01" min="0">

                <br><br>

                Category:
                <select name="category_id">
                    <option value="">All Categories</option>
        """

        for category in categories:
            content += f"""
                <option value="{category['category_id']}">
                    {escape(category['name'])}
                </option>
            """

        content += """
                </select>
                <br><br>

                <button type="submit">Search</button>
            </form>

            <br>
            <a href="/books">Back to Books</a>
        """

        return page("Search Books", content)

    finally:
        conn.close()

if __name__ == "__main__":
    app.run(debug=True)
