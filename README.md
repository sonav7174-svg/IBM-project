

# Identity Security Framework for EdTech (Flask)

## Overview

This project is a Flask-based web application implementing an identity security framework for an EdTech platform.
It provides authentication, role-based access control, and course management for admin, instructors, and students.

---

## Requirements

* Python 3.x
* pip

---

## Setup and Execution

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd <project-folder>
```

### 2. Create virtual environment (venv)

```bash
python -m venv venv
```

### 3. Activate virtual environment

**Windows:**

```bash
venv\Scripts\activate
```

**Linux / Mac:**

```bash
source venv/bin/activate
```

### 4. Install dependencies

```bash
pip install flask werkzeug
```

### 5. Run the application

```bash
python app.py
```

### 6. Open in browser

```
http://127.0.0.1:5000/
```

---

## Project Structure

```
app.py
edtech.db
templates/
    base.html
    auth/
    admin/
    instructor/
    courses/
```

---

## Wrapper Function Details

The project uses a custom wrapper function (decorator) to control access to routes.

### Purpose

* Restricts access to authenticated users
* Enforces role-based authorization
* Prevents unauthorized access to protected pages

### Example Concept

```python
from functools import wraps
from flask import session, redirect, url_for

def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def wrapped_function(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))
            if role and session.get("role") != role:
                return redirect(url_for("unauthorized"))
            return f(*args, **kwargs)
        return wrapped_function
    return decorator
```

### Usage

```python
@app.route("/admin")
@login_required(role="admin")
def admin_dashboard():
    return "Admin Page"
```

---

## Password Hashing

Passwords are not stored in plain text.
The project uses Werkzeug security utilities for hashing.

### Generate Password Hash

```python
from werkzeug.security import generate_password_hash

hashed_password = generate_password_hash("user_password")
```

### Verify Password

```python
from werkzeug.security import check_password_hash

check_password_hash(hashed_password, "user_password")
```

---

## Features

* User registration and login
* Role-based access control (admin, instructor, student)
* Secure password storage
* Course management system

---

## Notes

* SQLite database is used for simplicity
* Suitable for learning and small-scale applications
* Can be extended with advanced security features

---
