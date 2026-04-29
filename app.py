from flask import Flask, render_template, request, redirect, url_for, session, flash, g
import sqlite3
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "change-this-secret-key"
app.config["DATABASE"] = "edtech.db"


# -----------------------
# Database helpers
# -----------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(app.config["DATABASE"])
    cursor = db.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user', 'instructor', 'admin'))
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            instructor TEXT NOT NULL,
            description TEXT
        )
        """
    )

    # If table already existed without description, add it safely
    cursor.execute("PRAGMA table_info(courses)")
    course_columns = [row[1] for row in cursor.fetchall()]
    if "description" not in course_columns:
        cursor.execute("ALTER TABLE courses ADD COLUMN description TEXT")

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS enrollments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            UNIQUE(user_id, course_id),
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(course_id) REFERENCES courses(id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(course_id) REFERENCES courses(id)
        )
        """
    )

    # Seed default admin if not exists
    cursor.execute("SELECT id FROM users WHERE username = ?", ("admin",))
    admin_exists = cursor.fetchone()
    if not admin_exists:
        cursor.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            ("admin", generate_password_hash("admin123"), "admin"),
        )

    db.commit()
    db.close()


# -----------------------
# Auth decorators
# -----------------------
def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapper


def role_required(*allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in first.", "error")
                return redirect(url_for("login"))

            if session.get("role") not in allowed_roles:
                flash("You are not authorized to access this page.", "error")
                return redirect(url_for("home"))

            return view_func(*args, **kwargs)

        return wrapper

    return decorator


# -----------------------
# Auth routes
# -----------------------
@app.route("/")
def home():
    return redirect(url_for("courses_list"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "user")

        if not username or not password:
            flash("Username and password are required.", "error")
            return redirect(url_for("register"))

        if role not in ["user", "instructor"]:
            role = "user"

        db = get_db()
        cursor = db.cursor()

        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        existing = cursor.fetchone()
        if existing:
            flash("Username already exists.", "error")
            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            (username, hashed_password, role),
        )
        db.commit()

        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("auth/register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            flash("Logged in successfully.", "success")

            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            if user["role"] == "instructor":
                return redirect(url_for("instructor_dashboard"))
            return redirect(url_for("courses_list"))

        flash("Invalid username or password.", "error")
        return redirect(url_for("login"))

    return render_template("auth/login.html")


@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


# -----------------------
# User routes
# -----------------------
@app.route("/courses")
def courses_list():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM courses ORDER BY id DESC")
    courses = cursor.fetchall()

    enrolled_course_ids = set()
    if "user_id" in session:
        cursor.execute(
            "SELECT course_id FROM enrollments WHERE user_id = ?",
            (session["user_id"],),
        )
        enrolled_course_ids = {row["course_id"] for row in cursor.fetchall()}

    return render_template(
        "courses/list.html",
        courses=courses,
        enrolled_course_ids=enrolled_course_ids,
    )


@app.route("/courses/enroll/<int:course_id>", methods=["POST"])
@login_required
@role_required("user")
def enroll_course(course_id):
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT id FROM courses WHERE id = ?", (course_id,))
    course = cursor.fetchone()
    if not course:
        flash("Course not found.", "error")
        return redirect(url_for("courses_list"))

    cursor.execute(
        "SELECT id FROM enrollments WHERE user_id = ? AND course_id = ?",
        (session["user_id"], course_id),
    )
    duplicate = cursor.fetchone()

    if duplicate:
        flash("You are already enrolled in this course.", "error")
        return redirect(url_for("courses_list"))

    cursor.execute(
        "INSERT INTO enrollments (user_id, course_id) VALUES (?, ?)",
        (session["user_id"], course_id),
    )
    db.commit()

    flash("Enrollment successful.", "success")
    return redirect(url_for("my_courses"))


@app.route("/my-courses")
@login_required
@role_required("user")
def my_courses():
    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        """
        SELECT c.id, c.name, c.instructor
        FROM courses c
        INNER JOIN enrollments e ON c.id = e.course_id
        WHERE e.user_id = ?
        ORDER BY c.id DESC
        """,
        (session["user_id"],),
    )
    courses = cursor.fetchall()

    cursor.execute(
        "SELECT course_id, message FROM feedback WHERE user_id = ?",
        (session["user_id"],),
    )
    feedback_rows = cursor.fetchall()
    feedback_map = {row["course_id"]: row["message"] for row in feedback_rows}

    return render_template(
        "courses/my_courses.html",
        courses=courses,
        feedback_map=feedback_map,
    )


@app.route("/feedback/<int:course_id>", methods=["POST"])
@login_required
@role_required("user")
def add_feedback(course_id):
    message = request.form.get("message", "").strip()
    if not message:
        flash("Feedback message cannot be empty.", "error")
        return redirect(url_for("my_courses"))

    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        "SELECT id FROM enrollments WHERE user_id = ? AND course_id = ?",
        (session["user_id"], course_id),
    )
    enrolled = cursor.fetchone()

    if not enrolled:
        flash("You can only give feedback for enrolled courses.", "error")
        return redirect(url_for("my_courses"))

    cursor.execute(
        "INSERT INTO feedback (user_id, course_id, message) VALUES (?, ?, ?)",
        (session["user_id"], course_id, message),
    )
    db.commit()

    flash("Feedback submitted.", "success")
    return redirect(url_for("my_courses"))


# -----------------------
# Instructor routes
# -----------------------
@app.route("/instructor/dashboard")
@login_required
@role_required("instructor")
def instructor_dashboard():
    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        "SELECT * FROM courses WHERE instructor = ? ORDER BY id DESC",
        (session["username"],),
    )
    own_courses = cursor.fetchall()

    cursor.execute(
        """
        SELECT c.name AS course_name, u.username AS student_name
        FROM enrollments e
        INNER JOIN courses c ON e.course_id = c.id
        INNER JOIN users u ON e.user_id = u.id
        WHERE c.instructor = ?
        ORDER BY c.id DESC
        """,
        (session["username"],),
    )
    enrolled_students = cursor.fetchall()

    return render_template(
        "instructor/dashboard.html",
        own_courses=own_courses,
        enrolled_students=enrolled_students,
    )


# -----------------------
# Admin routes
# -----------------------
@app.route("/admin/dashboard")
@login_required
@role_required("admin")
def admin_dashboard():
    db = get_db()
    cursor = db.cursor()

    cursor.execute("SELECT COUNT(*) AS total FROM users")
    total_users = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM courses")
    total_courses = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM enrollments")
    total_enrollments = cursor.fetchone()["total"]

    cursor.execute(
        """
        SELECT e.id, u.username, c.name AS course_name
        FROM enrollments e
        INNER JOIN users u ON e.user_id = u.id
        INNER JOIN courses c ON e.course_id = c.id
        ORDER BY e.id DESC
        """
    )
    enrollments = cursor.fetchall()

    return render_template(
        "admin/dashboard.html",
        total_users=total_users,
        total_courses=total_courses,
        total_enrollments=total_enrollments,
        enrollments=enrollments,
    )


@app.route("/admin/courses", methods=["GET", "POST"])
@login_required
@role_required("admin")
def admin_courses():
    db = get_db()
    cursor = db.cursor()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        instructor = request.form.get("instructor", "").strip()
        description = request.form.get("description", "").strip()

        if not name or not instructor or not description:
            flash("Course name, instructor, and description are required.", "error")
            return redirect(url_for("admin_courses"))

        cursor.execute(
            "SELECT id FROM users WHERE username = ? AND role = ?",
            (instructor, "instructor"),
        )
        instructor_exists = cursor.fetchone()

        if not instructor_exists:
            flash("Instructor username not found.", "error")
            return redirect(url_for("admin_courses"))

        cursor.execute(
            "INSERT INTO courses (name, instructor, description) VALUES (?, ?, ?)",
            (name, instructor, description),
        )
        db.commit()
        flash("Course added successfully.", "success")
        return redirect(url_for("admin_courses"))

    cursor.execute("SELECT * FROM courses ORDER BY id DESC")
    courses = cursor.fetchall()

    cursor.execute("SELECT username FROM users WHERE role = ? ORDER BY username", ("instructor",))
    instructors = cursor.fetchall()

    return render_template(
        "admin/courses.html",
        courses=courses,
        instructors=instructors,
    )


@app.route("/admin/users")
@login_required
@role_required("admin")
def admin_users():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT id, username, role FROM users ORDER BY id DESC")
    users = cursor.fetchall()
    return render_template("admin/users.html", users=users)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
