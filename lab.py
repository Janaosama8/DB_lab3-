
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


# ---------------- LOGIN AND REGISTER ----------------

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
    return login_form()


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
    return redirect("/books")

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
            <a href="/authors">View Authors</a> |
            <a href="/add_book">Add Book</a> |
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


if __name__ == "__main__":
    app.run(debug=True)
