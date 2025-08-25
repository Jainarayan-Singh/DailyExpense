from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import re

app = Flask(__name__)
app.secret_key = "secret123"  # session ke liye

# --------- PostgreSQL Config ---------
# Render will give you connection string like:
# postgresql://username:password@hostname:port/dbname
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://username:password@hostname:port/dbname'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --------- Database Models ---------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    transactions = db.relationship('Transaction', backref='user', lazy=True)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    purpose = db.Column(db.String(100))
    location = db.Column(db.String(100))
    date = db.Column(db.Date)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# --------- Helper Functions ---------
def load_users():
    """Fetch all users from DB"""
    users = User.query.all()
    return {u.username: u.password for u in users}

def save_user(username, password):
    """Add a new user to DB"""
    new_user = User(username=username, password=password)
    db.session.add(new_user)
    db.session.commit()

# --------- Routes ---------
@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        # Password validation
        if password != confirm_password:
            error = "Passwords do not match. Please try again."
        elif len(password) < 8:
            error = "Password must be at least 8 characters long."
        elif not re.search(r"[A-Z]", password):
            error = "Password must contain at least one uppercase letter."
        elif not re.search(r"[0-9]", password):
            error = "Password must contain at least one number."
        elif not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            error = "Password must contain at least one special character."
        else:
            users = load_users()
            if username in users:
                error = "Username already exists. Try login."
            else:
                save_user(username, password)
                return redirect(url_for("login"))

    return render_template("register.html", error=error)


@app.route("/", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        users = load_users()
        if username in users and users[username] == password:
            session["user"] = username
            return redirect(url_for("dashboard"))
        else:
            error = "Invalid username or password"

    return render_template("login.html", error=error)


@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("dashboard.html")


@app.route("/add", methods=["GET", "POST"])
def add_transaction():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        amount = float(request.form["amount"])
        purpose = request.form["purpose"]
        location = request.form["location"]
        date_str = request.form["date"]
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()

        user = User.query.filter_by(username=session["user"]).first()
        new_transaction = Transaction(
            amount=amount,
            purpose=purpose,
            location=location,
            date=date_obj,
            user_id=user.id
        )
        db.session.add(new_transaction)
        db.session.commit()

        return redirect(url_for("dashboard"))

    return render_template("add.html")


@app.route("/track")
def track():
    if "user" not in session:
        return redirect(url_for("login"))

    username = session["user"]
    user = User.query.filter_by(username=username).first()
    query = Transaction.query.filter_by(user_id=user.id)

    # Filters
    purpose = request.args.get("purpose")
    location = request.args.get("location")
    min_amount = request.args.get("min_amount")
    max_amount = request.args.get("max_amount")
    date = request.args.get("date")

    if purpose and purpose.strip():
        query = query.filter(Transaction.purpose.ilike(f"%{purpose}%"))
    if location and location.strip():
        query = query.filter(Transaction.location.ilike(f"%{location}%"))
    if min_amount and min_amount.strip():
        query = query.filter(Transaction.amount >= float(min_amount))
    if max_amount and max_amount.strip():
        query = query.filter(Transaction.amount <= float(max_amount))
    if date and date.strip():
        date_obj = datetime.strptime(date, "%Y-%m-%d").date()
        query = query.filter(Transaction.date == date_obj)

    transactions = query.all()

    # Stats
    total = sum(t.amount for t in transactions)
    avg = round(total / len(transactions), 2) if transactions else 0
    count = len(transactions)

    chart_labels = [t.date.strftime("%Y-%m-%d") for t in transactions]
    chart_data = [t.amount for t in transactions]

    # Convert transactions to dict for template
    transactions_dict = [
        {"Date": t.date.strftime("%Y-%m-%d"), "Amount": t.amount, "Purpose": t.purpose, "Location": t.location}
        for t in transactions
    ]

    return render_template("track.html",
                           transactions=transactions_dict,
                           total=total,
                           avg=avg,
                           count=count,
                           chart_labels=chart_labels,
                           chart_data=chart_data)


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))


# --------- Initialize DB & Run ---------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()  # Create tables if not exists
    app.run(debug=True)
