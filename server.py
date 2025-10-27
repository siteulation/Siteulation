import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from flask import Flask, request, session, redirect, url_for, render_template, flash, abort, Response, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash

# Optional: Google Generative AI (Gemini)
# pip install google-generativeai
import google.generativeai as genai

APP_NAME = "siteulation"
BASE_DIR = Path(__file__).parent.resolve()
DB_PATH = BASE_DIR / "siteulation.db"
PROJECTS_DIR = BASE_DIR / "projects"

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
GEMINI_API_KEY = os.environ.get("APIKEY")

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = SECRET_KEY

# Configure Gemini if available
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    GEMINI_MODEL = genai.GenerativeModel("gemini-1.5-flash")
else:
    GEMINI_MODEL = None

###############################################################################
# Database
###############################################################################
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        username TEXT NOT NULL,
        title TEXT NOT NULL,
        slug TEXT NOT NULL,
        html_content TEXT NOT NULL,
        views INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(user_id, slug),
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)
    conn.commit()
    conn.close()

PROJECTS_DIR.mkdir(exist_ok=True)
init_db()

###############################################################################
# Helpers
###############################################################################
USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,20}$")
SLUG_RE = re.compile(r"^[a-z0-9\-]{3,50}$")

def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, username FROM users WHERE id=?", (uid,))
    row = c.fetchone()
    conn.close()
    return row

def require_login():
    if not current_user():
        flash("Please log in to continue.", "error")
        return redirect(url_for("login"))

def write_project_files(username: str, slug: str, html: str):
    user_dir = PROJECTS_DIR / username
    proj_dir = user_dir / slug
    proj_dir.mkdir(parents=True, exist_ok=True)
    (proj_dir / "index.html").write_text(html, encoding="utf-8")

def sanitize_slug(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9\-]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s[:50] or "site"

def gemini_generate_html(prompt: str) -> str:
    if GEMINI_MODEL is None:
        # Fallback simple template
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{APP_NAME} Generated Site</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;600&display=swap" rel="stylesheet">
  <style>
    :root {{ --fg:#111; --bg:#fff; --muted:#666; }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; font-family:"Noto Sans", system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; color:var(--fg); background:var(--bg); }}
    header {{ padding:2rem; border-bottom:1px solid #eee; }}
    main {{ max-width:900px; margin:2rem auto; padding:0 1rem; }}
    h1 {{ margin:0 0 0.5rem; }}
    p.muted {{ color:var(--muted); }}
    a.btn {{ display:inline-block; padding:0.6rem 1rem; border:1px solid #111; border-radius:8px; text-decoration:none; color:#111; transition:transform .08s ease; }}
    a.btn:active {{ transform:scale(0.98); }}
  </style>
  <script type="importmap">
  {{
    "imports": {{
      "lit": "https://esm.sh/lit@3"
    }}
  }}
  </script>
</head>
<body>
  <header>
    <h1>Generated Site</h1>
    <p class="muted">Prompt: {prompt[:140]}</p>
  </header>
  <main>
    <p>This is a placeholder page because the Gemini API key was not configured.</p>
    <a class="btn" href="/">Back to {APP_NAME}</a>
  </main>
</body>
</html>"""
    system_instructions = (
        "You are an assistant that outputs a complete, production-ready, self-contained website as a single HTML file. "
        "Requirements:\n"
        "- Use a simple, clean design on white or black background only. Avoid color unless explicitly needed.\n"
        "- Use modern, accessible, semantic HTML.\n"
        "- Include minimal CSS in a <style> tag. Avoid garish gradients, purple backgrounds, and Comic Sans. Prefer Noto Sans.\n"
        "- Include any JS via CDN with an import map if necessary. Do not use base64 data URLs.\n"
        "- Keep animations subtle and performant.\n"
        "- Do not include external images unless via safe, hotlink CDN placeholders; prefer SVG inline for icons.\n"
        "- No server calls; everything should run client-side.\n"
        "- The result must be a single HTML document that renders well on mobile and desktop."
    )
    user_prompt = f"Build a single-file website implementing the following idea:\n\n{prompt}\n\nDeliver exactly one complete HTML document."
    resp = GEMINI_MODEL.generate_content([system_instructions, user_prompt])
    html = resp.text or ""
    # If model wrapped in code fences, strip them
    html = html.strip()
    if html.startswith("```"):
        html = re.sub(r"^```[a-zA-Z0-9]*\n", "", html)
        html = re.sub(r"\n```$", "", html)
    return html

###############################################################################
# Routes
###############################################################################
@app.route("/")
def home():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
      SELECT username, slug, title, views, created_at
      FROM projects
      ORDER BY views DESC, created_at DESC
      LIMIT 24
    """)
    projects = [dict(r) for r in c.fetchall()]
    conn.close()
    return render_template("index.html", app_name=APP_NAME, user=current_user(), projects=projects)

@app.route("/api/projects")
def api_projects():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
      SELECT username, slug, title, views, created_at
      FROM projects
      ORDER BY views DESC, created_at DESC
      LIMIT 24
    """)
    rows = c.fetchall()
    conn.close()
    projects = [dict(r) for r in rows]
    return {"projects": projects}

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not USERNAME_RE.match(username):
            flash("Username must be 3-20 chars (letters, numbers, underscore).", "error")
            return redirect(url_for("signup"))
        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return redirect(url_for("signup"))
        conn = get_db()
        c = conn.cursor()
        try:
            c.execute(
                "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                (username, generate_password_hash(password), datetime.utcnow().isoformat())
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            flash("Username is already taken.", "error")
            return redirect(url_for("signup"))
        # Log in
        c.execute("SELECT id FROM users WHERE username=?", (username,))
        row = c.fetchone()
        conn.close()
        session["user_id"] = row["id"]
        flash("Welcome to siteulation!", "success")
        return redirect(url_for("studio"))
    # GET: render the signup page
    return render_template("signup.html", app_name=APP_NAME, user=current_user())

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, username, password_hash FROM users WHERE username=?", (username,))
        user = c.fetchone()
        conn.close()
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            flash("Logged in.", "success")
            return redirect(url_for("studio"))
        flash("Invalid credentials.", "error")
        return redirect(url_for("login"))
    # GET: render the login page
    return render_template("login.html", app_name=APP_NAME, user=current_user())

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Logged out.", "success")
    return redirect(url_for("home"))

@app.route("/studio")
def studio():
    if not current_user():
        return redirect(url_for("login"))
    # GET: render the studio page
    return render_template("studio.html", app_name=APP_NAME, user=current_user())

@app.route("/api/generate", methods=["POST"])
def api_generate():
    user = current_user()
    if not user:
        return {"error": "auth_required"}, 401
    data = request.get_json(force=True, silent=True) or {}
    title = (data.get("title") or "").strip()
    prompt = (data.get("prompt") or "").strip()
    slug_in = (data.get("slug") or "").strip()
    if not title or not prompt:
        return {"error": "missing_fields"}, 400
    slug = sanitize_slug(slug_in or title)
    if not SLUG_RE.match(slug):
        return {"error": "invalid_slug"}, 400

    # Unique per user
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM projects WHERE user_id=? AND slug=?", (user["id"], slug))
    if c.fetchone():
        conn.close()
        return {"error": "slug_exists"}, 409

    # Generate HTML using Gemini
    try:
        html = gemini_generate_html(prompt)
    except Exception as e:
        return {"error": "generation_failed", "details": str(e)}, 500

    now = datetime.utcnow().isoformat()
    c.execute("""
        INSERT INTO projects (user_id, username, title, slug, html_content, views, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, 0, ?, ?)
    """, (user["id"], user["username"], title, slug, html, now, now))
    conn.commit()
    conn.close()

    # Also write to filesystem for convenience
    write_project_files(user["username"], slug, html)

    url = url_for("project", username=user["username"], slug=slug)
    return {"ok": True, "url": url, "slug": slug}

@app.route("/@<username>")
def profile(username):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, username FROM users WHERE username=?", (username,))
    u = c.fetchone()
    if not u:
        conn.close()
        abort(404)
    c.execute("""
      SELECT title, slug, views, created_at
      FROM projects
      WHERE user_id=?
      ORDER BY created_at DESC
    """, (u["id"],))
    projects = c.fetchall()
    conn.close()
    return render_template("profile.html", app_name=APP_NAME, profile_user=u, projects=projects, user=current_user())

@app.route("/@<username>/<slug>")
def project(username, slug):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
      SELECT p.id, p.html_content FROM projects p
      WHERE p.username=? AND p.slug=?
    """, (username, slug))
    row = c.fetchone()
    if not row:
        conn.close()
        abort(404)
    # increment views
    c.execute("UPDATE projects SET views = views + 1 WHERE id=?", (row["id"],))
    conn.commit()
    conn.close()

    # Try to serve the generated file from disk
    proj_file = PROJECTS_DIR / username / slug / "index.html"
    if proj_file.is_file():
        return send_from_directory(proj_file.parent, proj_file.name)

    # Fallback to DB content if file is missing
    html = row["html_content"]
    return Response(html, mimetype="text/html")

# Serve saved project files directly if needed (optional)
@app.route("/projects/<path:subpath>")
def serve_project_file(subpath):
    target = PROJECTS_DIR / subpath
    if target.is_file():
        return send_from_directory(target.parent, target.name)
    abort(404)

###############################################################################
# Run
###############################################################################
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
