from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response
import os
import psycopg
from psycopg.rows import dict_row
from werkzeug.security import generate_password_hash, check_password_hash

SECRET_KEY = os.environ.get("SECRET_KEY", "dev")
APP_NAME = "siteulation"
DATABASE_URL = os.environ.get("DATABASE_URL")

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = SECRET_KEY
app.url_map.strict_slashes = False

def get_db():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)

def init_db():
    with get_db() as conn, conn.cursor() as cur:
        # Users table
        cur.execute("""
        create table if not exists users (
            id serial primary key,
            username varchar(20) unique not null,
            password_hash text not null,
            created_at timestamp default now()
        );
        """)
        # Projects table
        cur.execute("""
        create table if not exists projects (
            id serial primary key,
            user_id int not null references users(id) on delete cascade,
            title varchar(120) not null,
            slug varchar(80) not null,
            html text not null,
            views int not null default 0,
            created_at timestamp default now(),
            unique(user_id, slug)
        );
        """)
        # Helpful index
        cur.execute("create index if not exists idx_projects_views on projects(views desc);")

@app.before_request
def ensure_db():
    # Initialize once per process
    if not getattr(app, "_db_inited", False) and DATABASE_URL:
        init_db()
        app._db_inited = True

def current_user():
    return session.get("user")

def fetch_user_by_username(username):
    with get_db() as conn, conn.cursor() as cur:
        cur.execute("select id, username, password_hash from users where username = %s", (username,))
        return cur.fetchone()

def fetch_user_by_id(user_id):
    with get_db() as conn, conn.cursor() as cur:
        cur.execute("select id, username from users where id = %s", (user_id,))
        return cur.fetchone()

@app.get("/")
def home():
    if not DATABASE_URL:
        flash("Database is not configured. Set DATABASE_URL to enable accounts and projects.", "error")
        return render_template("index.html", projects=[], app_name=APP_NAME, user=current_user())
    with get_db() as conn, conn.cursor() as cur:
        cur.execute("""
        select p.title, p.slug, p.views, u.username
        from projects p
        join users u on u.id = p.user_id
        order by p.views desc, p.created_at desc
        limit 24
        """)
        projects = cur.fetchall()
    return render_template("index.html", projects=projects, app_name=APP_NAME, user=current_user())

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if not DATABASE_URL:
        flash("Sign up is unavailable: DATABASE_URL is not set.", "error")
        return redirect(url_for("home"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            flash("Username and password are required.", "error")
            return redirect(url_for("signup"))

        existing = fetch_user_by_username(username)
        if existing:
            flash("Username already taken.", "error")
            return redirect(url_for("signup"))

        pw_hash = generate_password_hash(password)
        with get_db() as conn, conn.cursor() as cur:
            cur.execute(
                "insert into users (username, password_hash) values (%s, %s) returning id, username",
                (username, pw_hash)
            )
            user_row = cur.fetchone()
        session["user"] = {"id": user_row["id"], "username": user_row["username"]}
        flash("Signed up successfully.", "success")
        return redirect(url_for("studio"))
    return render_template("signup.html", app_name=APP_NAME, user=current_user())

@app.route("/login", methods=["GET", "POST"])
def login():
    if not DATABASE_URL:
        flash("Login is unavailable: DATABASE_URL is not set.", "error")
        return redirect(url_for("home"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            flash("Username and password are required.", "error")
            return redirect(url_for("login"))

        user_row = fetch_user_by_username(username)
        if not user_row or not check_password_hash(user_row["password_hash"], password):
            flash("Invalid username or password.", "error")
            return redirect(url_for("login"))

        session["user"] = {"id": user_row["id"], "username": user_row["username"]}
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
    if not DATABASE_URL:
        flash("Studio is unavailable: DATABASE_URL is not set.", "error")
        return redirect(url_for("home"))
    if not current_user():
        flash("Please log in to use the Studio.", "error")
        return redirect(url_for("login"))
    return render_template("studio.html", app_name=APP_NAME, user=current_user())

@app.post("/api/generate")
def api_generate():
    if not DATABASE_URL:
        return jsonify({"error": "Service unavailable: DATABASE_URL is not set"}), 503
    cu = current_user()
    if not cu:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "Untitled").strip()
    slug = (data.get("slug") or title.lower().replace(" ", "-")).strip()[:50] or "untitled"
    prompt = (data.get("prompt") or "").strip()

    # For now, create a minimal HTML using the prompt for content
    generated_html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;600&display=swap" rel="stylesheet">
<style>
  body {{ font-family: "Noto Sans", system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin:0; padding:32px; color:#111; background:#fff; line-height:1.6; }}
  .wrap {{ max-width: 900px; margin: 0 auto; }}
  h1 {{ margin:0 0 12px; font-size: 2rem; }}
  p.muted {{ color:#666; }}
  section {{ margin-top: 20px; }}
  a.btn {{ display:inline-block; border:1px solid #111; padding:8px 12px; border-radius:8px; text-decoration:none; color:#111; }}
</style>
</head>
<body>
  <div class="wrap">
    <h1>{title}</h1>
    <p class="muted">Generated site</p>
    <section>
      <h2>Overview</h2>
      <p>{prompt or "This is your generated site. Edit and regenerate to refine."}</p>
    </section>
  </div>
</body>
</html>"""

    # Upsert-like behavior: if slug exists for this user, overwrite html and title
    with get_db() as conn, conn.cursor() as cur:
        # Ensure user still exists
        cur.execute("select id from users where id = %s", (cu["id"],))
        owner = cur.fetchone()
        if not owner:
            return jsonify({"error": "User not found"}), 400

        try:
            cur.execute("""
                insert into projects (user_id, title, slug, html)
                values (%s, %s, %s, %s)
                on conflict (user_id, slug)
                do update set title = excluded.title, html = excluded.html
                returning slug
            """, (cu["id"], title, slug, generated_html))
            saved = cur.fetchone()
            slug = saved["slug"]
        except Exception as e:
            return jsonify({"error": "Failed to save project"}), 500

    url = f"/@{cu['username']}/{slug}"
    return jsonify({"url": url})

@app.get("/@<username>")
def profile(username):
    if not DATABASE_URL:
        flash("Profiles are unavailable: DATABASE_URL is not set.", "error")
        return render_template("profile.html", profile_user={"username": username}, projects=[], app_name=APP_NAME, user=current_user()), 200
    user_row = fetch_user_by_username(username)
    if not user_row:
        return render_template("profile.html", profile_user={"username": username}, projects=[], app_name=APP_NAME, user=current_user()), 200
    with get_db() as conn, conn.cursor() as cur:
        cur.execute("""
        select title, slug, views
        from projects
        where user_id = %s
        order by created_at desc
        """, (user_row["id"],))
        projects = cur.fetchall()
    return render_template("profile.html", profile_user={"username": username}, projects=projects, app_name=APP_NAME, user=current_user())

@app.get("/@<username>/<slug>")
def view_project(username, slug):
    if not DATABASE_URL:
        return render_template("404.html"), 404
    user_row = fetch_user_by_username(username)
    if not user_row:
        return render_template("404.html"), 404
    with get_db() as conn, conn.cursor() as cur:
        cur.execute("""
        select id, html, views from projects where user_id = %s and slug = %s
        """, (user_row["id"], slug))
        proj = cur.fetchone()
        if not proj:
            return render_template("404.html"), 404
        # increment views
        cur.execute("update projects set views = views + 1 where id = %s", (proj["id"],))
        html = proj["html"]
    # Serve the stored HTML directly
    return Response(html, mimetype="text/html")
