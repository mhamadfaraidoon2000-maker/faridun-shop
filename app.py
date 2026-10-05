import os
import sqlite3
from flask import Flask, render_template, request, redirect, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "faridun-secret")

BASE = os.path.dirname(__file__)
DB = os.path.join(BASE, "faridun.db")
UP = os.path.join(BASE, "static", "uploads")
os.makedirs(UP, exist_ok=True)

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init():
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS settings(
        id INTEGER PRIMARY KEY,
        shop_name TEXT
    );

    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT,
        active INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS categories(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        brand TEXT,
        name TEXT
    );

    CREATE TABLE IF NOT EXISTS products(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        brand TEXT,
        category_id INTEGER,
        name TEXT,
        code TEXT,
        buy REAL,
        sell REAL,
        image TEXT
    );
    """)

    if c.execute("SELECT count(*) FROM settings").fetchone()[0] == 0:
        c.execute(
            "INSERT INTO settings(shop_name) VALUES(?)",
            ("فرۆشگای فریدون",)
        )

    if c.execute("SELECT count(*) FROM users").fetchone()[0] == 0:
        c.execute(
            "INSERT INTO users(username,password,role) VALUES(?,?,?)",
            ("admin", generate_password_hash("admin123"), "admin")
        )

    c.commit()
    c.close()

def me():
    if "uid" not in session:
        return None

    c = db()
    u = c.execute(
        "SELECT * FROM users WHERE id=? AND active=1",
        (session["uid"],)
    ).fetchone()
    c.close()
    return u

def isadmin():
    u = me()
    return u and u["role"] == "admin"

@app.context_processor
def ctx():
    c = db()
    s = c.execute("SELECT shop_name FROM settings").fetchone()
    c.close()
    return {
        "shop_name": s["shop_name"],
        "me": me()
    }

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        c = db()
        u = c.execute(
            "SELECT * FROM users WHERE username=?",
            (request.form["username"],)
        ).fetchone()
        c.close()

        if u and u["active"] and check_password_hash(
            u["password"],
            request.form["password"]
        ):
            session["uid"] = u["id"]
            return redirect("/home")

        flash("ناوی بەکارهێنەر یان وشەی نهێنی هەڵەیە")

    return render_template("login.html")

@app.get("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.get("/home")
def home():
    if not me():
        return redirect("/")

    q = request.args.get("q", "")
    c = db()

    products = c.execute("""
        SELECT p.*, c.name AS cat
        FROM products p
        LEFT JOIN categories c ON c.id = p.category_id
        WHERE p.name LIKE ? OR p.code LIKE ?
        ORDER BY p.id DESC
    """, (f"%{q}%", f"%{q}%")).fetchall()

    cats = c.execute(
        "SELECT * FROM categories ORDER BY brand, name"
    ).fetchall()

    c.close()

    return render_template(
        "home.html",
        products=products,
        cats=cats,
        q=q
    )

@app.post("/category")
def category():
    if not isadmin():
        return "Forbidden", 403

    c = db()
    c.execute(
        "INSERT INTO categories(brand,name) VALUES(?,?)",
        (request.form["brand"], request.form["name"])
    )
    c.commit()
    c.close()

    return redirect("/home")

@app.post("/product")
def product():
    if not isadmin():
        return "Forbidden", 403

    fn = ""
    f = request.files.get("image")

    if f and f.filename:
        fn = secure_filename(f.filename)
        f.save(os.path.join(UP, fn))

    c = db()
    c.execute("""
        INSERT INTO products(
            brand, category_id, name, code, buy, sell, image
        )
        VALUES(?,?,?,?,?,?,?)
    """, (
        request.form["brand"],
        request.form.get("category_id") or None,
        request.form["name"],
        request.form["code"],
        request.form.get("buy") or 0,
        request.form.get("sell") or 0,
        fn
    ))

    c.commit()
    c.close()

    return redirect("/home")

@app.post("/delete/<int:i>")
def delete(i):
    if not isadmin():
        return "Forbidden", 403

    c = db()
    c.execute("DELETE FROM products WHERE id=?", (i,))
    c.commit()
    c.close()

    return redirect("/home")

@app.post("/settings")
def settings():
    if not isadmin():
        return "Forbidden", 403

    c = db()
    c.execute(
        "UPDATE settings SET shop_name=?",
        (request.form["shop_name"],)
    )
    c.commit()
    c.close()

    return redirect("/home")

@app.get("/employees")
def employees():
    if not isadmin():
        return "Forbidden", 403

    c = db()
    users = c.execute(
        "SELECT * FROM users WHERE role='employee'"
    ).fetchall()
    c.close()

    return render_template("employees.html", users=users)

@app.post("/employee/add")
def addemp():
    if not isadmin():
        return "Forbidden", 403

    c = db()

    try:
        c.execute(
            "INSERT INTO users(username,password,role) VALUES(?,?,?)",
            (
                request.form["username"],
                generate_password_hash(request.form["password"]),
                "employee"
            )
        )
        c.commit()
    except sqlite3.IntegrityError:
        flash("ئەم ناوە پێشتر هەیە")

    c.close()
    return redirect("/employees")

@app.post("/employee/toggle/<int:i>")
def toggle(i):
    if not isadmin():
        return "Forbidden", 403

    c = db()
    c.execute(
        "UPDATE users SET active=1-active WHERE id=? AND role='employee'",
        (i,)
    )
    c.commit()
    c.close()

    return redirect("/employees")

@app.post("/employee/delete/<int:i>")
def delem(i):
    if not isadmin():
        return "Forbidden", 403

    c = db()
    c.execute(
        "DELETE FROM users WHERE id=? AND role='employee'",
        (i,)
    )
    c.commit()
    c.close()

    return redirect("/employees")

init()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
