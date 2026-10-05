"""
Expense Tracker web app (Flask + MongoDB) with user accounts

    pip install flask pymongo
    python app.py          ->  http://localhost:5000

Env vars (optional):
    MONGO_URI    default mongodb://localhost:27017
    MONGO_DB     default expense_tracker
    SECRET_KEY   signs login sessions. Set a fixed value in production;
                 if unset, a random one is used and everyone is logged out on restart.

MongoDB collections: users, expenses (each expense has a user_id), counters.
"""
import os
import re
import secrets
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, jsonify, redirect, request, send_from_directory, session
from pymongo import ASCENDING, MongoClient, ReturnDocument
from pymongo.errors import DuplicateKeyError
from werkzeug.security import check_password_hash, generate_password_hash

MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://sankarper0907_db_user:ExUBKTIOy5N8MbD0@cluster0.dhglvda.mongodb.net")
DB_NAME = os.getenv("MONGO_DB", "expense_tracker")
BASE_DIR = Path(__file__).resolve().parent

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY") or secrets.token_hex(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  PERMANENT_SESSION_LIFETIME=timedelta(days=7))

db = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)[DB_NAME]
try:
    db.users.create_index([("username_lower", ASCENDING)], unique=True)
    db.expenses.create_index([("user_id", ASCENDING), ("date", ASCENDING)])
except Exception as err:  # keep pages loadable; API calls will show the DB error
    print(f"WARNING: could not reach MongoDB at startup: {err}")


# ---------- Auth ----------
def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "uid" not in session:
            return jsonify(error="Please sign in."), 401
        return fn(*args, **kwargs)
    return wrapper


def start_session(uid, username):
    session.clear()
    session.permanent = True
    session["uid"], session["username"] = uid, username


def credentials():
    d = request.get_json(silent=True) or {}
    return (d.get("username") or "").strip(), d.get("password") or ""


@app.post("/api/register")
def register():
    username, password = credentials()
    is_email = len(username) <= 254 and re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", username)
    is_name = re.fullmatch(r"[A-Za-z0-9_.-]{3,30}", username)
    if not (is_email or is_name):
        return jsonify(error="Enter a valid email address, or a username of 3-30 letters, numbers, . _ -"), 400
    if len(password) < 8:
        return jsonify(error="Password must be at least 8 characters."), 400
    try:
        res = db.users.insert_one({
            "username": username, "username_lower": username.lower(),
            "password_hash": generate_password_hash(password), "created_at": datetime.utcnow()})
    except DuplicateKeyError:
        return jsonify(error="That username is taken. Choose another."), 409
    start_session(str(res.inserted_id), username)
    return jsonify(username=username), 201


@app.post("/api/login")
def login():
    username, password = credentials()
    user = db.users.find_one({"username_lower": username.lower()})
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify(error="Incorrect username or password."), 401
    start_session(str(user["_id"]), user["username"])
    return jsonify(username=user["username"])


@app.post("/api/logout")
def logout():
    session.clear()
    return "", 204


@app.get("/api/me")
@login_required
def me():
    return jsonify(username=session["username"])


# ---------- Pages ----------
@app.get("/")
def index():
    if "uid" not in session:
        return redirect("/login")
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/login")
def login_page():
    if "uid" in session:
        return redirect("/")
    return send_from_directory(BASE_DIR, "login.html")


# ---------- Expenses (always scoped to the signed-in user) ----------
def clean(doc):
    return {k: doc[k] for k in ("id", "date", "category", "amount", "description")}


def parse(data):
    """Validate request JSON; returns (fields, error)."""
    try:
        amount = round(float(data.get("amount")), 2)
        date = datetime.strptime(data.get("date", ""), "%Y-%m-%d").strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return None, "Enter a positive amount and a valid date."
    category = (data.get("category") or "").strip().title()
    if amount <= 0 or not category:
        return None, "Enter a positive amount and choose a category."
    return {"amount": amount, "date": date, "category": category,
            "description": (data.get("description") or "").strip() or "-"}, None


def build_query():
    q = {"user_id": session["uid"]}
    month, cat = request.args.get("month", ""), request.args.get("category", "")
    if month:
        q["date"] = {"$regex": f"^{re.escape(month)}"}
    if cat:
        q["category"] = {"$regex": f"^{re.escape(cat)}$", "$options": "i"}
    return q


@app.get("/api/expenses")
@login_required
def list_expenses():
    rows = db.expenses.find(build_query()).sort([("date", -1), ("id", -1)])
    return jsonify([clean(r) for r in rows])


@app.post("/api/expenses")
@login_required
def add_expense():
    fields, err = parse(request.get_json(silent=True) or {})
    if err:
        return jsonify(error=err), 400
    uid = session["uid"]
    seq = db.counters.find_one_and_update(
        {"_id": f"expenses:{uid}"}, {"$inc": {"seq": 1}}, upsert=True,
        return_document=ReturnDocument.AFTER)["seq"]
    fields.update(id=seq, user_id=uid, created_at=datetime.utcnow())
    db.expenses.insert_one(fields)
    return jsonify(clean(fields)), 201


@app.put("/api/expenses/<int:eid>")
@login_required
def edit_expense(eid):
    fields, err = parse(request.get_json(silent=True) or {})
    if err:
        return jsonify(error=err), 400
    res = db.expenses.update_one({"id": eid, "user_id": session["uid"]}, {"$set": fields})
    if not res.matched_count:
        return jsonify(error="Expense not found."), 404
    return jsonify(clean({**fields, "id": eid}))


@app.delete("/api/expenses/<int:eid>")
@login_required
def delete_expense(eid):
    res = db.expenses.delete_one({"id": eid, "user_id": session["uid"]})
    if not res.deleted_count:
        return jsonify(error="Expense not found."), 404
    return "", 204


@app.get("/api/summary")
@login_required
def summary():
    pipeline = [{"$match": build_query()},
                {"$group": {"_id": "$category", "total": {"$sum": "$amount"}, "count": {"$sum": 1}}},
                {"$sort": {"total": -1}}]
    rows = [{"category": r["_id"], "total": round(r["total"], 2), "count": r["count"]}
            for r in db.expenses.aggregate(pipeline)]
    return jsonify(rows=rows, total=round(sum(r["total"] for r in rows), 2),
                   count=sum(r["count"] for r in rows))


if __name__ == "__main__":
    app.run(debug=True)