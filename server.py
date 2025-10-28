from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import os

SECRET_KEY = os.environ.get("SECRET_KEY", "dev")
APP_NAME = "siteulation"

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = SECRET_KEY
app.url_map.strict_slashes = False

def current_user():
    return session.get("user")

@app.get("/")
def home():
    return render_template("index.html", projects=[], app_name=APP_NAME, user=current_user())

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        if not username:
            flash("Username is required.", "error")
            return redirect(url_for("signup"))
        session["user"] = {"username": username}
        flash("Signed up successfully.", "success")
        return redirect(url_for("studio"))
    return render_template("signup.html", app_name=APP_NAME, user=current_user())

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        if not username:
            flash("Username is required.", "error")
            return redirect(url_for("login"))
        session["user"] = {"username": username}
        flash("Logged in.", "success")
        return redirect(url_for("studio"))
    return render_template("login.html", app_name=APP_NAME, user=current_user())

@app.post("/logout")
def logout():
    session.pop("user", None)
    flash("Logged out.", "success")
    return redirect(url_for("home"))

@app.get("/studio")
def studio():
    if not current_user():
        flash("Please log in to use the Studio.", "error")
        return redirect(url_for("login"))
    return render_template("studio.html", app_name=APP_NAME, user=current_user())

@app.post("/api/generate")
def api_generate():
    if not current_user():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(force=True) or {}
    title = (data.get("title") or "Untitled").strip()
    slug = (data.get("slug") or title.lower().replace(" ", "-")[:50]).strip() or "untitled"
    url = f"/@{current_user()['username']}/{slug}"
    return jsonify({"url": url})
