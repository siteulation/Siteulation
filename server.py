from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import os

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = SECRET_KEY
app.url_map.strict_slashes = False

SECRET_KEY = os.environ.get("SECRET_KEY", "dev")
APP_NAME = "siteulation"

PROJECTS = {}  # key: (username, slug) -> {"title": str, "html": str}

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

@app.post("/api/projects")
def create_project():
    if not current_user():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(force=True) or {}
    title = (data.get("title") or "Untitled").strip()
    slug = (data.get("slug") or title.lower().replace(" ", "-")[:50]).strip() or "untitled"
    key = (current_user()["username"], slug)
    PROJECTS[key] = {"title": title, "html": "<!doctype html><html><head><meta charset='utf-8'><title>{}</title><meta name='viewport' content='width=device-width, initial-scale=1'><link rel='preconnect' href='https://fonts.googleapis.com'><link href='https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;600&display=swap' rel='stylesheet'><style>body{font-family:'Noto Sans',system-ui;-webkit-font-smoothing:antialiased;margin:0;padding:24px;line-height:1.6}h1{margin:0 0 12px}</style></head><body><h1>{}</h1><p class='muted'>prompt to create your site!</p></body></html>".format(title, title)}
    return jsonify({"url": f"/@{key[0]}/{key[1]}"}), 201

@app.route("/@<username>/<slug>/fullpage")
def project_fullpage(username, slug):
    key = (username, slug)
    proj = PROJECTS.get(key)
    if not proj:
        return "Not Found", 404
    return proj["html"]

@app.route("/@<username>/<slug>", methods=["GET", "POST"])
def project_embed(username, slug):
    key = (username, slug)
    proj = PROJECTS.get(key)
    if not proj:
        return "Not Found", 404
    if request.method == "POST":
        prompt = (request.form.get("prompt") or "").strip()
        if prompt:
            html = generate_html_from_prompt(proj["title"], prompt)
            PROJECTS[key]["html"] = html
            flash("Page updated.", "success")
        return redirect(f"/@{username}/{slug}")
    return render_template("project_embed.html", app_name=APP_NAME, user=current_user(), proj=proj, username=username, slug=slug)

import google.generativeai as genai
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY", ""))
def generate_html_from_prompt(title, prompt):
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        resp = model.generate_content(f"Create a single self-contained HTML file for a website titled '{title}'. Use clean styles, no external images. Implement the following:\n\n{prompt}\n\nReturn only valid HTML.")
        html = resp.text or ""
        if "<html" not in html:
            html = f"<!doctype html><html><head><meta charset='utf-8'><title>{title}</title></head><body><pre>{html}</pre></body></html>"
        return html
    except Exception:
        return f"<!doctype html><html><head><meta charset='utf-8'><title>{title}</title></head><body><p>Failed to generate. Try again.</p></body></html>"
