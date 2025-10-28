const state = {
  currentUser: null
};
// Add API base override (set window.SITEULATION_API = 'https://your-backend.example.com' in HTML if needed)
const API_BASE = typeof window !== "undefined" && window.SITEULATION_API ? window.SITEULATION_API.replace(/\/$/, "") : "";

// Persist current user locally (no passwords)
const USER_KEY = "siteulation.currentUser";
function readLocalUser() {
  try { return JSON.parse(localStorage.getItem(USER_KEY)); } catch { return null; }
}
function writeLocalUser(u) {
  if (!u) localStorage.removeItem(USER_KEY);
  else localStorage.setItem(USER_KEY, JSON.stringify(u));
}
// Initialize from local cache for instant nav rendering
state.currentUser = readLocalUser();

function setTitle(t) {
  document.title = t ? `${t} – siteulation` : "siteulation";
}

// Router infra
const routes = [];
function route(pattern, handler) {
  routes.push({ pattern, handler });
}

function matchRoute(path) {
  for (const r of routes) {
    if (typeof r.pattern === "string" && r.pattern === path) {
      return { handler: r.handler, params: {} };
    }
    if (r.pattern instanceof RegExp) {
      const m = path.match(r.pattern);
      if (m) {
        return { handler: r.handler, params: m.groups || {} };
      }
    }
  }
  return null;
}

async function navigateTo(href, replace = false) {
  const url = new URL(href, location.origin);
  (replace ? history.replaceState : history.pushState).call(history, {}, '', url.pathname);
  await router();
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
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
  let projects = []; let popular = [];
  try {
    const [resP, resU] = await Promise.all([
      fetch(`${API_BASE}/api/projects`, { headers: { "Accept": "application/json" }, credentials: "include" }),
      fetch(`${API_BASE}/api/popular-users`, { headers: { "Accept": "application/json" }, credentials: "include" })
    ]);
    if (resP.ok) projects = (await resP.json()).projects || [];
    if (resU.ok) popular = (await resU.json()).users || [];
  } catch { /* ignore */ }
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
    <h1>Most popular users</h1>
    ${popular.length === 0 ? `
      <p class="muted">No users yet.</p>
    ` : `
      <ul class="list">
        ${popular.map(u => `
          <li>
            <a data-link href="/@${encodeURIComponent(u.username)}">@${escapeHtml(u.username)}</a>
            <span class="muted"> · ${Number(u.views||0)} views · ${Number(u.projects||0)} projects</span>
          </li>
        `).join("")}
      </ul>
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
  el.querySelector("#login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    try {
      const res = await fetch(`${API_BASE}/login`, {
        method: "POST",
        body: fd,
        credentials: "include"
      });
      if (res.ok) {
        await loadSession();
        navigateTo("/studio");
      } else {
        alert("Invalid credentials.");
      }
    } catch {
      alert("Network error.");
    }
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
  el.querySelector("#signup-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    try {
      const res = await fetch(`${API_BASE}/signup`, {
        method: "POST",
        body: fd,
        credentials: "include"
      });
      if (res.ok) {
        await loadSession();
        navigateTo("/studio");
      } else {
        alert("Signup failed.");
      }
    } catch {
      alert("Network error.");
    }
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
    const payload = {
      title: (fd.get("title") || "").toString().trim(),
      slug: (fd.get("slug") || "").toString().trim(),
      prompt: (fd.get("prompt") || "").toString().trim()
    };
    if (!payload.title || !payload.prompt) {
      alert("Please fill in title and prompt.");
      return;
    }
    form.querySelector('button[type="submit"]').disabled = true;
    try {
      const res = await fetch(`${API_BASE}/api/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        credentials: "include"
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        alert(data?.error || "Generation failed");
        return;
      }
      const url = data.url.startsWith("http") ? data.url : `${API_BASE}${data.url}`;
      link.href = url;
      link.textContent = url;
      result.hidden = false;
      window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
    } catch {
      alert("Network error.");
    } finally {
      form.querySelector('button[type="submit"]').disabled = false;
    }
  });
});

route(/^\/@(?<username>[A-Za-z0-9_]{3,20})$/, async (el, { username }) => {
  setTitle(`@${username}`);
  // Render server-backed profile page via simple list using /api/projects (already includes username on items)
  let userProjects = [];
  try {
    const res = await fetch(`${API_BASE}/api/projects`, { credentials: "include" });
    if (res.ok) {
      const data = await res.json();
      userProjects = (data.projects || []).filter(p => p.username === username);
    }
  } catch {}
  el.innerHTML = `
    <h1>@${escapeHtml(username)}</h1>
    <h2 class="sub">Projects</h2>
    ${userProjects.length === 0 ? `
      <p class="muted">No projects yet.</p>
    ` : `
      <ul class="list">
        ${userProjects.map(p => `
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
  const url = `${API_BASE}/@${encodeURIComponent(username)}/${encodeURIComponent(slug)}`;
  el.innerHTML = `
    <div class="row" style="margin-top:12px">
      <a class="btn" data-link href="/">← Back</a>
    </div>
    <iframe title="${escapeHtml(slug)}" style="width:100%;height:70vh;border:1px solid var(--border);border-radius:12px;margin-top:12px" src="${url}"></iframe>
  `;
});

// Session bootstrap
async function loadSession() {
  try {
    const res = await fetch(`${API_BASE}/api/me`, { credentials: "include" });
    if (res.ok) {
      const data = await res.json();
      state.currentUser = data.user;
      if (state.currentUser) writeLocalUser(state.currentUser);
      else writeLocalUser(null);
    } else {
      state.currentUser = readLocalUser(); // keep local if server unreachable
    }
  } catch {
    // Network error: fall back to local cache
    state.currentUser = readLocalUser();
  }
}

function renderNav() {
  const nav = document.getElementById("nav"); if (!nav) return;
  nav.innerHTML = state.currentUser ? `
    <a data-link href="/studio">Studio</a>
    <a data-link href="/@${encodeURIComponent(state.currentUser.username)}">Profile</a>
    <form class="inline" id="logout-form"><button class="btn" type="submit">Logout</button></form>
  ` : `
    <a data-link href="/login">Log in</a>
    <a class="btn" data-link href="/signup">Sign up</a>
  `;
  const f = nav.querySelector("#logout-form"); if (f) f.addEventListener("submit", async (e) => {
    e.preventDefault();
    writeLocalUser(null);
    await fetch(`${API_BASE}/logout`, { method:"POST", credentials:"include"});
    await loadSession();
    renderNav();
    navigateTo("/", true);
  });
}

async function router() {
  const el = document.getElementById("app");
  const m = matchRoute(location.pathname);
  if (!m) { setTitle("Not found"); el.innerHTML = "<h1>Not found</h1>"; return; }
  await m.handler(el, m.params || {});
  attachLinkHandlers(el);
}

attachGlobalLinkInterceptor();
window.addEventListener("popstate", router);
renderNav();
await loadSession();
renderNav();
router();
