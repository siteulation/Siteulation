from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import os
import google.generativeai as genai

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = SECRET_KEY
app.url_map.strict_slashes = False

SECRET_KEY = os.environ.get("SECRET_KEY", "dev")
APP_NAME = "siteulation"
GENAI_API_KEY = os.environ.get("GOOGLE_API_KEY")
if GENAI_API_KEY:
    genai.configure(api_key=GENAI_API_KEY)

# simple in-memory store: {(username, slug): {"title": str, "html": str, "views": int}}
PROJECTS = {}

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
    user = current_user()["username"]
    key = (user, slug)
    if key not in PROJECTS:
        PROJECTS[key] = {
            "title": title,
            "html": """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>prompt to create your site!</title><link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;600&display=swap" rel="stylesheet"><style>body{font-family:'Noto Sans',system-ui;max-width:800px;margin:40px auto;padding:0 16px;line-height:1.6}h1{font-size:1.8rem}</style></head><body><h1>prompt to create your site!</h1><p>Use the sidebar on the embed page to enter a prompt. Each prompt will replace this page with a newly generated site.</p></body></html>""",
            "views": 0,
        }
    url = f"/@{user}/{slug}"
    return jsonify({"url": url})

@app.get("/@<username>/<slug>")
def project_embed(username, slug):
    key = (username, slug)
    if key not in PROJECTS:
        return redirect(url_for("home"))
    PROJECTS[key]["views"] += 1
    return render_template("project_embed.html", app_name=APP_NAME, user=current_user(), project=PROJECTS[key], username=username, slug=slug)

@app.get("/@<username>/<slug>/fullpage")
def project_fullpage(username, slug):
    key = (username, slug)
    proj = PROJECTS.get(key)
    if not proj:
        return "<h1>Not Found</h1>", 404
    return proj["html"], 200, {"Content-Type": "text/html; charset=utf-8"}

@app.post("/@<username>/<slug>/prompt")
def project_prompt(username, slug):
    if not current_user() or current_user()["username"] != username:
        return jsonify({"error": "Unauthorized"}), 401
    key = (username, slug)
    proj = PROJECTS.get(key)
    if not proj:
        return jsonify({"error": "Project not found"}), 404
    data = request.get_json(force=True) or {}
    prompt = (data.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"error": "Prompt required"}), 400
    try:
        if GENAI_API_KEY:
            model = genai.GenerativeModel("gemini-2.5-flash")
            resp = model.generate_content(f"Create a single, self-contained HTML file (no external JS) for this website:\n{prompt}\nRequirements:\n- Use Noto Sans.\n- Clean, simple white background.\n- No garish gradients or complex animations.\n- Include clear headings and content.\nReturn ONLY the HTML.")
            html = resp.text or proj["html"]
        else:
            html = f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>{proj['title']}</title><link rel='preconnect' href='https://fonts.googleapis.com'><link href='https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;600&display=swap' rel='stylesheet'><style>body{{font-family:'Noto Sans',system-ui;max-width:800px;margin:40px auto;padding:0 16px;line-height:1.6}}</style></head><body><h1>{proj['title']}</h1><p>(Dev mode) Would generate for prompt:</p><pre>{prompt}</pre></body></html>"
        PROJECTS[key]["html"] = html
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)[:200]}), 500
