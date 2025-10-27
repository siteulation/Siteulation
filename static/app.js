const state = {
  users: [],
  projects: [],
  currentUser: null
};
// Add API base override (set window.SITEULATION_API = 'https://your-backend.example.com' in HTML if needed)
const API_BASE = typeof window !== "undefined" && window.SITEULATION_API ? window.SITEULATION_API.replace(/\/$/, "") : "";

// Storage helpers
const storeKey = "siteulation_store_v1";
function loadStore() {
  try {
    const raw = localStorage.getItem(storeKey);
    if (raw) {
      const data = JSON.parse(raw);
      state.users = data.users || [];
      state.projects = data.projects || [];
      state.currentUser = data.currentUser || null;
    }
  } catch {}
}
function saveStore() {
  localStorage.setItem(storeKey, JSON.stringify({
    users: state.users,
    projects: state.projects,
    currentUser: state.currentUser
  }));
}

// Basic utils
function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
function slugify(s) {
  return (s || "")
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\-]+/g, "-")
    .replace(/\-+/g, "-")
    .replace(/^\-|\-$/g, "")
    .slice(0, 50) || "site";
}

// Router
const routes = [];
function route(path, handler) {
  routes.push({ path, handler });
}
function matchRoute(pathname) {
  // Patterns in order of specificity
  for (const r of routes) {
    if (typeof r.path === "string" && r.path === pathname) {
      return { handler: r.handler, params: {} };
    }
    if (r.path instanceof RegExp) {
      const m = pathname.match(r.path);
      if (m) return { handler: r.handler, params: m.groups || {} };
    }
  }
  return null;
}
function renderNav() {
  const nav = document.getElementById("nav");
  if (!nav) return;
  if (state.currentUser) {
    nav.innerHTML = `
      <a data-link href="/studio">Studio</a>
      <a data-link href="/@${encodeURIComponent(state.currentUser.username)}">Profile</a>
      <button class="btn" id="logout-btn" type="button">Logout</button>
    `;
    nav.querySelector("#logout-btn").addEventListener("click", () => {
      state.currentUser = null;
      saveStore();
      navigateTo("/");
    });
  } else {
    nav.innerHTML = `
      <a data-link href="/studio">Studio</a>
      <a data-link href="/login">Log in</a>
      <a class="btn" data-link href="/signup">Sign up</a>
    `;
  }
}
function setTitle(t) {
  document.title = t ? `${t} – siteulation` : "siteulation";
}
async function navigateTo(url, replace = false) {
  if (replace) history.replaceState(null, "", url);
  else history.pushState(null, "", url);
  await router();
}
async function router() {
  renderNav();
  const app = document.getElementById("app");
  const pathname = window.location.pathname;
  const matched = matchRoute(pathname);
  if (!matched) {
    // 404 view
    setTitle("Not found");
    app.innerHTML = `
      <h1>Not found</h1>
      <p class="muted">The page you're looking for doesn't exist.</p>
      <p><a class="btn" data-link href="/">Go home</a></p>
    `;
    attachLinkHandlers(app);
    return;
  }
  await matched.handler(app, matched.params);
  attachLinkHandlers(app);
}

// Link interception
function isInternalLink(a) {
  return a.origin === window.location.origin;
}
function attachGlobalLinkInterceptor() {
  document.addEventListener("click", (e) => {
    const a = e.target.closest("a[data-link]");
    if (!a) return;
    if (!isInternalLink(a)) return;
    const href = a.getAttribute("href");
    if (!href || href.startsWith("#") || href.startsWith("mailto:") || href.startsWith("tel:")) return;
    e.preventDefault();
    navigateTo(href);
  });
}
function attachLinkHandlers(scope = document) {
  scope.querySelectorAll("a").forEach(a => {
    if (!a.hasAttribute("data-link") && isInternalLink(a)) {
      a.setAttribute("data-link", "");
    }
  });
}

// Views
route("/", async (el) => {
  setTitle("");
  // Try server projects first, fallback to local
  let projects = [];
  try {
    const res = await fetch(`${API_BASE}/api/projects`, { headers: { "Accept": "application/json" } });
    if (res.ok) {
      const data = await res.json();
      projects = data.projects || [];
    }
  } catch {
    // ignore
  }
  if (!projects.length) {
    projects = state.projects
      .slice()
      .sort((a, b) => (b.views || 0) - (a.views || 0))
      .slice(0, 24)
      .map(p => ({
        username: p.username,
        slug: p.slug,
        title: p.title,
        views: p.views || 0
      }));
  }
  el.innerHTML = `
    <h1>Most viewed projects</h1>
    ${projects.length === 0 ? `
      <p class="muted">No projects yet. Sign up and create your first site in the Studio.</p>
    ` : `
      <div class="grid">
        ${projects.map(p => `
          <a class="card" data-link href="/@${encodeURIComponent(p.username)}/${encodeURIComponent(p.slug)}">
            <div class="card-body">
              <h3>${escapeHtml(p.title)}</h3>
              <p class="muted">by @${escapeHtml(p.username)}</p>
            </div>
            <div class="card-meta">
              <span>${Number(p.views || 0)} views</span>
            </div>
          </a>
        `).join("")}
      </div>
    `}
  `;
});

route("/login", async (el) => {
  if (state.currentUser) return navigateTo("/studio", true);
  setTitle("Log in");
  el.innerHTML = `
    <h1>Log in</h1>
    <form id="login-form" class="form">
      <label>
        <span>Username</span>
        <input name="username" required autocomplete="username">
      </label>
      <label>
        <span>Password</span>
        <input name="password" type="password" required autocomplete="current-password">
      </label>
      <button class="btn" type="submit">Log in</button>
    </form>
    <p class="muted">No account? <a data-link href="/signup">Sign up</a></p>
  `;
  el.querySelector("#login-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const username = (fd.get("username") || "").toString().trim();
    const password = (fd.get("password") || "").toString();
    const user = state.users.find(u => u.username === username);
    if (!user || user.password !== password) {
      alert("Invalid credentials.");
      return;
    }
    state.currentUser = { id: user.id, username: user.username };
    saveStore();
    navigateTo("/studio");
  });
});

route("/signup", async (el) => {
  if (state.currentUser) return navigateTo("/studio", true);
  setTitle("Sign up");
  el.innerHTML = `
    <h1>Create your account</h1>
    <form id="signup-form" class="form">
      <label>
        <span>Username</span>
        <input name="username" minlength="3" maxlength="20" pattern="[A-Za-z0-9_]{3,20}" required autocomplete="username">
      </label>
      <label>
        <span>Password</span>
        <input name="password" type="password" minlength="6" required autocomplete="new-password">
      </label>
      <button class="btn" type="submit">Sign up</button>
    </form>
    <p class="muted">Already have an account? <a data-link href="/login">Log in</a></p>
  `;
  el.querySelector("#signup-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const username = (fd.get("username") || "").toString().trim();
    const password = (fd.get("password") || "").toString();
    if (!/^[A-Za-z0-9_]{3,20}$/.test(username)) {
      alert("Username must be 3-20 chars (letters, numbers, underscore).");
      return;
    }
    if (state.users.some(u => u.username === username)) {
      alert("Username is already taken.");
      return;
    }
    const user = { id: crypto.randomUUID(), username, password, createdAt: new Date().toISOString() };
    state.users.push(user);
    state.currentUser = { id: user.id, username: user.username };
    saveStore();
    navigateTo("/studio");
  });
});

route("/studio", async (el) => {
  if (!state.currentUser) return navigateTo("/login", true);
  setTitle("Studio");
  el.innerHTML = `
    <h1>Studio</h1>
    <p class="muted">Describe the website you want. We'll generate a complete, self-contained HTML file.</p>
    <form id="gen-form" class="form">
      <label>
        <span>Title</span>
        <input id="title" name="title" required maxlength="120" placeholder="My Awesome Site">
      </label>
      <label>
        <span>Slug (optional)</span>
        <input id="slug" name="slug" maxlength="50" placeholder="my-awesome-site">
      </label>
      <label>
        <span>Prompt</span>
        <textarea id="prompt" name="prompt" rows="8" required placeholder="Explain what the site should do, sections, interactions, etc."></textarea>
      </label>
      <button class="btn" type="submit">Generate</button>
    </form>
    <div id="result" class="result" hidden>
      <p>Done! View your site:</p>
      <p><a id="site-link" data-link href="#" class="btn">Open site</a></p>
    </div>
  `;
  const form = el.querySelector("#gen-form");
  const result = el.querySelector("#result");
  const link = el.querySelector("#site-link");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(form);
    const title = (fd.get("title") || "").toString().trim();
    const prompt = (fd.get("prompt") || "").toString().trim();
    const slugIn = (fd.get("slug") || "").toString().trim();
    const slug = slugify(slugIn || title);
    if (!title || !prompt) {
      alert("Please fill in title and prompt.");
      return;
    }

    // Try server API first
    let serverOk = false;
    try {
      const res = await fetch(`${API_BASE}/api/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, slug, prompt }),
        credentials: "include"
      });
      if (res.ok) {
        const data = await res.json();
        link.href = data.url.startsWith("http") ? data.url : `${API_BASE}${data.url}`;
        link.textContent = link.href;
        result.hidden = false;
        serverOk = true;
      }
    } catch { /* ignore */ }

    if (!serverOk) {
      // Local fallback: generate simple placeholder HTML
      const html = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>${escapeHtml(title)}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    :root { --fg:#111; --bg:#fff; --muted:#666; --border:#ebebeb; }
    * { box-sizing: border-box; }
    body { margin:0; color:var(--fg); background:var(--bg); font-family:"Noto Sans", system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; line-height:1.5; }
    header { padding:20px; border-bottom:1px solid var(--border); }
    main { max-width:900px; margin:20px auto; padding:0 16px; }
    .muted { color:var(--muted); }
    .btn { display:inline-block; border:1px solid var(--fg); padding:8px 12px; border-radius:8px; text-decoration:none; color:inherit; }
  </style>
</head>
<body>
  <header><h1>${escapeHtml(title)}</h1><p class="muted">Generated locally. Prompt preview: ${escapeHtml(prompt.slice(0, 140))}</p></header>
  <main>
    <p>This project was created without a running server; content is stored in your browser.</p>
    <p><a class="btn" href="/">Back to siteulation</a></p>
  </main>
</body>
</html>`;
      // store project locally
      const username = state.currentUser.username;
      if (state.projects.some(p => p.username === username && p.slug === slug)) {
        alert("Slug already exists for your account.");
        return;
      }
      state.projects.push({
        id: crypto.randomUUID(),
        userId: state.currentUser.id,
        username,
        title,
        slug,
        html,
        views: 0,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      });
      saveStore();
      const url = `/@${encodeURIComponent(username)}/${encodeURIComponent(slug)}`;
      link.href = url;
      link.textContent = url;
      result.hidden = false;
    }
    window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
  });
});

route(/^\/@(?<username>[A-Za-z0-9_]{3,20})$/, async (el, { username }) => {
  setTitle(`@${username}`);
  // Try server profile if available (no-op on static)
  // Fallback to local
  const projects = state.projects
    .filter(p => p.username === username)
    .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
  el.innerHTML = `
    <h1>@${escapeHtml(username)}</h1>
    <h2 class="sub">Projects</h2>
    ${projects.length === 0 ? `
      <p class="muted">No projects yet.</p>
    ` : `
      <ul class="list">
        ${projects.map(p => `
          <li>
            <a data-link href="/@${encodeURIComponent(username)}/${encodeURIComponent(p.slug)}"><strong>${escapeHtml(p.title)}</strong></a>
            <span class="muted"> · ${Number(p.views || 0)} views</span>
          </li>
        `).join("")}
      </ul>
    `}
  `;
});

route(/^\/@(?<username>[A-Za-z0-9_]{3,20})\/(?<slug>[a-z0-9\-]{1,50})$/, async (el, { username, slug }) => {
  setTitle(`${username}/${slug}`);
  // Try server page first
  let servedByServer = false;
  try {
    const url = `${API_BASE}/@${encodeURIComponent(username)}/${encodeURIComponent(slug)}`;
    const res = await fetch(url, { method: "GET" });
    if (res.ok && res.headers.get("content-type")?.includes("text/html")) {
      const html = await res.text();
      el.innerHTML = `
        <div class="row" style="margin-top:12px">
          <a class="btn" data-link href="/">← Back</a>
        </div>
        <iframe title="${escapeHtml(slug)}" style="width:100%;height:70vh;border:1px solid var(--border);border-radius:12px;margin-top:12px" srcdoc="${html.replaceAll('"', "&quot;")}"></iframe>
      `;
      servedByServer = true;
    }
  } catch { /* ignore */ }

  if (!servedByServer) {
    const proj = state.projects.find(p => p.username === username && p.slug === slug);
    if (!proj) {
      el.innerHTML = `
        <h1>Project not found</h1>
        <p class="muted">We couldn't find @${escapeHtml(username)}/${escapeHtml(slug)}.</p>
        <p><a class="btn" data-link href="/">Go home</a></p>
      `;
      return;
    }
    // increment local view
    proj.views = (proj.views || 0) + 1;
    proj.updatedAt = new Date().toISOString();
    saveStore();
    el.innerHTML = `
      <div class="row" style="margin-top:12px">
        <a class="btn" data-link href="/">← Back</a>
      </div>
      <iframe title="${escapeHtml(slug)}" style="width:100%;height:70vh;border:1px solid var(--border);border-radius:12px;margin-top:12px" srcdoc="${proj.html.replaceAll('"', "&quot;")}"></iframe>
    `;
  }
});

// Boot
loadStore();
attachGlobalLinkInterceptor();
window.addEventListener("popstate", router);
renderNav();
router();
