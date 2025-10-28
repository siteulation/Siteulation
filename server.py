import os
import re
from datetime import datetime
from pathlib import Path
from flask import Flask, request, session, redirect, url_for, render_template, flash, abort, Response, send_from_directory, g
from werkzeug.security import generate_password_hash, check_password_hash

# Optional: Google Generative AI (Gemini)
# pip install google-generativeai
import google.generativeai as genai

# NEW: Postgres via psycopg
import psycopg
from psycopg.rows import dict_row

APP_NAME = "siteulation"
BASE_DIR = Path(__file__).parent.resolve()
PROJECTS_DIR = BASE_DIR / "projects"

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
GEMINI_API_KEY = os.environ.get("APIKEY")
DB_URL = os.environ.get("DBURL")  # Render Postgres internal URL

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = SECRET_KEY

# Configure Gemini if available
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    GEMINI_MODEL = genai.GenerativeModel("gemini-2.5-flash")
else:
    GEMINI_MODEL = None

###############################################################################
# Database
###############################################################################
def get_db():
    if "db" not in g:
        if not DB_URL:
            raise RuntimeError("DBURL environment variable not set")
        g.db = psycopg.connect(DB_URL, autocommit=False, row_factory=dict_row)
    return g.db

@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    conn = get_db()
    with conn.cursor() as c:
        c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL
        )
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            username TEXT NOT NULL,
            title TEXT NOT NULL,
            slug TEXT NOT NULL,
            html_content TEXT NOT NULL,
            views INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL,
            UNIQUE(user_id, slug)
        )
        """)
    conn.commit()

PROJECTS_DIR.mkdir(exist_ok=True)
with app.app_context():
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
    with conn.cursor() as c:
        c.execute("SELECT id, username FROM users WHERE id=%s", (uid,))
        row = c.fetchone()
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
    with conn.cursor() as c:
        c.execute("""
          SELECT username, slug, title, views, created_at
          FROM projects
          ORDER BY views DESC, created_at DESC
          LIMIT 24
        """)
        projects = [dict(r) for r in c.fetchall()]
    return render_template("index.html", app_name=APP_NAME, user=current_user(), projects=projects)

@app.route("/studio")
def studio():
    if not current_user():
        return redirect(url_for("login"))
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

    conn = get_db()
    with conn.cursor() as c:
        c.execute("SELECT id FROM projects WHERE user_id=%s AND slug=%s", (user["id"], slug))
        if c.fetchone():
            return {"error": "slug_exists"}, 409

    try:
        html = gemini_generate_html(prompt)
    except Exception as e:
        return {"error": "generation_failed", "details": str(e)}, 500

    now = datetime.utcnow().isoformat()
    try:
        with conn.cursor() as c:
            c.execute("""
                INSERT INTO projects (user_id, username, title, slug, html_content, views, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, 0, %s, %s)
            """, (user["id"], user["username"], title, slug, html, now, now))
        conn.commit()
    except Exception as e:
        conn.rollback()
        return {"error": "db_error", "details": str(e)}, 500

    # Also write to filesystem for convenience
    write_project_files(user["username"], slug, html)

    url = url_for("project", username=user["username"], slug=slug)
    return {"ok": True, "url": url, "slug": slug}

@app.route("/@<username>")
def profile(username):
    conn = get_db()
    with conn.cursor() as c:
        c.execute("SELECT id, username FROM users WHERE username=%s", (username,))
        u = c.fetchone()
        if not u:
            abort(404)
        c.execute("""
          SELECT title, slug, views, created_at
          FROM projects
          WHERE user_id=%s
          ORDER BY created_at DESC
        """, (u["id"],))
        projects = c.fetchall()
    return render_template("profile.html", app_name=APP_NAME, profile_user=u, projects=projects, user=current_user())

@app.route("/@<username>/<slug>")
def project(username, slug):
    conn = get_db()
    with conn.cursor() as c:
        c.execute("""
          SELECT p.id, p.html_content FROM projects p
          WHERE p.username=%s AND p.slug=%s
        """, (username, slug))
        row = c.fetchone()
        if not row:
            abort(404)
        c.execute("UPDATE projects SET views = views + 1 WHERE id=%s", (row["id"],))
    conn.commit()

    proj_file = PROJECTS_DIR / username / slug / "index.html"
    if proj_file.is_file():
        return send_from_directory(proj_file.parent, proj_file.name)

    html = row["html_content"]
    return Response(html, mimetype="text/html")

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
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)