import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "nutritrack-secret-2024")

DATABASE = os.path.join(os.path.dirname(__file__), "nutritrack.db")

SAMPLE_FOODS = [
    ("Chicken Breast", 165, 31, 0, 3.6, "Protein", "Lean grilled chicken breast, excellent protein source"),
    ("Brown Rice", 216, 5, 45, 1.8, "Grains", "Cooked brown rice, complex carbohydrates for sustained energy"),
    ("Avocado", 160, 2, 9, 15, "Fats", "Fresh avocado, rich in healthy monounsaturated fats"),
    ("Whole Egg", 78, 6, 0.6, 5, "Protein", "Large whole egg, complete protein with essential nutrients"),
    ("Greek Yogurt", 59, 10, 3.6, 0.4, "Dairy", "Plain non-fat Greek yogurt, probiotic-rich dairy"),
    ("Salmon", 208, 20, 0, 13, "Protein", "Atlantic salmon fillet, omega-3 fatty acids powerhouse"),
    ("Sweet Potato", 86, 1.6, 20, 0.1, "Vegetables", "Baked sweet potato, rich in beta-carotene and fiber"),
    ("Oats", 389, 17, 66, 7, "Grains", "Rolled oats, high fiber whole grain for breakfast"),
    ("Banana", 89, 1.1, 23, 0.3, "Fruits", "Fresh banana, natural sugars and potassium-rich"),
    ("Almonds", 579, 21, 22, 50, "Nuts", "Raw almonds, nutrient-dense snack with healthy fats"),
    ("Broccoli", 34, 2.8, 7, 0.4, "Vegetables", "Fresh broccoli, antioxidant-packed cruciferous vegetable"),
    ("Quinoa", 120, 4.4, 21, 1.9, "Grains", "Cooked quinoa, complete plant-based protein and grain"),
    ("Lentils", 116, 9, 20, 0.4, "Legumes", "Cooked green lentils, iron-rich plant protein"),
    ("Cottage Cheese", 98, 11, 3.4, 4.3, "Dairy", "Low-fat cottage cheese, versatile high-protein dairy"),
    ("Spinach", 23, 2.9, 3.6, 0.4, "Vegetables", "Fresh spinach leaves, iron and vitamin K powerhouse"),
]


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def init_db():
    with app.app_context():
        db = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS foods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                calories REAL NOT NULL,
                protein REAL NOT NULL,
                carbs REAL NOT NULL,
                fats REAL NOT NULL,
                category TEXT NOT NULL,
                description TEXT
            )
        """)
        count = db.execute("SELECT COUNT(*) FROM foods").fetchone()[0]
        if count == 0:
            db.executemany(
                "INSERT INTO foods (name, calories, protein, carbs, fats, category, description) VALUES (?,?,?,?,?,?,?)",
                SAMPLE_FOODS
            )
        db.commit()
        db.close()


def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


@app.route("/")
def home():
    db = get_db()
    featured = db.execute("SELECT * FROM foods ORDER BY RANDOM() LIMIT 6").fetchall()
    return render_template("home.html", featured=featured)


@app.route("/foods")
def foods():
    db = get_db()
    query = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    sql = "SELECT * FROM foods WHERE 1=1"
    params = []
    if query:
        sql += " AND name LIKE ?"
        params.append(f"%{query}%")
    if category:
        sql += " AND category = ?"
        params.append(category)
    sql += " ORDER BY name"
    all_foods = db.execute(sql, params).fetchall()
    categories = db.execute("SELECT DISTINCT category FROM foods ORDER BY category").fetchall()
    return render_template("foods.html", foods=all_foods, categories=categories, query=query, selected_category=category)


@app.route("/calculators", methods=["GET", "POST"])
def calculators():
    db = get_db()
    all_foods = db.execute("SELECT * FROM foods ORDER BY name").fetchall()
    nutrition_result = None
    bmi_result = None

    if request.method == "POST":
        calc_type = request.form.get("calc_type")

        if calc_type == "nutrition":
            food_id = request.form.get("food_id")
            grams = request.form.get("grams", type=float)
            if food_id and grams and grams > 0:
                food = db.execute("SELECT * FROM foods WHERE id = ?", [food_id]).fetchone()
                if food:
                    factor = grams / 100
                    nutrition_result = {
                        "food": food,
                        "grams": grams,
                        "calories": round(food["calories"] * factor, 1),
                        "protein": round(food["protein"] * factor, 1),
                        "carbs": round(food["carbs"] * factor, 1),
                        "fats": round(food["fats"] * factor, 1),
                    }
            else:
                flash("Please select a food and enter valid grams.", "danger")

        elif calc_type == "bmi":
            height = request.form.get("height", type=float)
            weight = request.form.get("weight", type=float)
            if height and weight and height > 0 and weight > 0:
                bmi = weight / ((height / 100) ** 2)
                bmi = round(bmi, 1)
                if bmi < 18.5:
                    category = "Underweight"
                    color = "text-blue-500"
                elif bmi < 25:
                    category = "Normal Weight"
                    color = "text-emerald-500"
                elif bmi < 30:
                    category = "Overweight"
                    color = "text-yellow-500"
                else:
                    category = "Obese"
                    color = "text-red-500"
                bmi_result = {"bmi": bmi, "category": category, "color": color, "height": height, "weight": weight}
            else:
                flash("Please enter valid height and weight values.", "danger")

    return render_template("calculators.html", foods=all_foods, nutrition_result=nutrition_result, bmi_result=bmi_result)


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        if not username or not email or not password:
            flash("All fields are required.", "danger")
        elif password != confirm:
            flash("Passwords do not match.", "danger")
        elif len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
        else:
            db = get_db()
            existing = db.execute("SELECT id FROM users WHERE username=? OR email=?", [username, email]).fetchone()
            if existing:
                flash("Username or email already taken.", "danger")
            else:
                hashed = generate_password_hash(password)
                db.execute("INSERT INTO users (username, email, password) VALUES (?,?,?)", [username, email, hashed])
                db.commit()
                flash("Account created! Please log in.", "success")
                return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username=? OR email=?", [identifier, identifier]).fetchone()
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            flash(f"Welcome back, {user['username']}!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid username/email or password.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    total_foods = db.execute("SELECT COUNT(*) FROM foods").fetchone()[0]
    categories = db.execute("SELECT COUNT(DISTINCT category) FROM foods").fetchone()[0]
    return render_template("dashboard.html", total_foods=total_foods, categories=categories)


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
