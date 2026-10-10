/* FORMFIT AUTH/HISTORY V2 — isolated account UI */
(() => {
  const $ = id => document.getElementById(id);
  let registerMode = false;

  function openAuth() {
    $("authOverlay")?.classList.add("open");
    $("authOverlay")?.setAttribute("aria-hidden","false");
  }
  function closeAuth() {
    $("authOverlay")?.classList.remove("open");
    $("authOverlay")?.setAttribute("aria-hidden","true");
  }
  function setMessage(text) { if ($("authMessage")) $("authMessage").textContent = text || ""; }

  async function getMe() {
    const r = await fetch("/api/auth/me", {credentials:"same-origin"});
    if (!r.ok) return null;
    return await r.json();
  }

  function renderStats(rows) {
    const reps = rows.reduce((s,x)=>s + Number(x.reps || 0), 0);
    const avg = rows.length ? Math.round(rows.reduce((s,x)=>s + Number(x.score || 0),0)/rows.length) : 0;
    $("historyStats").innerHTML = `
      <div class="history-stat"><span>SESSIONS</span><strong>${rows.length}</strong></div>
      <div class="history-stat"><span>REPS</span><strong>${reps}</strong></div>
      <div class="history-stat"><span>AVG SCORE</span><strong>${avg}</strong></div>`;
  }

  async function openHistory() {
    const me = await getMe();
    if (!me || !me.authenticated) { openAuth(); return; }
    const r = await fetch("/api/history", {credentials:"same-origin"});
    if (!r.ok) { setMessage("Could not load history."); openAuth(); return; }
    const data = await r.json();
    const rows = Array.isArray(data.history) ? data.history : [];
    renderStats(rows);
    $("historyList").innerHTML = rows.length ? rows.map(x => `
      <article class="history-item">
        <div class="history-item-head">
          <strong>${escapeHtml(x.exercise || "Workout")}</strong>
          <time>${escapeHtml(x.created_at || "")}</time>
        </div>
        <div class="history-item-meta">
          <span>${Number(x.reps || 0)} reps</span>
          <span>Score ${Math.round(Number(x.score || 0))}</span>
          <span>${Math.round(Number(x.calories || 0))} kcal</span>
        </div>
      </article>`).join("") : `<div class="history-empty">No workouts saved yet.</div>`;
    $("historyDrawer").classList.add("open");
    $("historyDrawer").setAttribute("aria-hidden","false");
  }

  function escapeHtml(v) {
    return String(v).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
  }

  async function submitAuth(e) {
    e.preventDefault();
    const email = $("authEmail").value.trim();
    const password = $("authPassword").value;
    const endpoint = registerMode ? "/api/auth/register" : "/api/auth/login";
    setMessage("Please wait…");
    try {
      const r = await fetch(endpoint, {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        credentials:"same-origin",
        body:JSON.stringify({email,password})
      });
      const data = await r.json().catch(()=>({}));
      if (!r.ok) { setMessage(data.error || "Authentication failed."); return; }
      setMessage("Signed in.");
      closeAuth();
    } catch (_) {
      setMessage("Server connection failed.");
    }
  }

  $("accountBtn")?.addEventListener("click", openHistory);

  // Automatically show Login / Sign Up when the site opens
  // and no authenticated session exists.
  async function showAuthOnFirstLoad() {
    try {
      const me = await getMe();
      if (!me || !me.authenticated) {
        registerMode = false;
        $("authTitle").textContent = "Sign in";
        $("authSubmit").textContent = "Sign in";
        $("authSwitch").textContent = "Create an account";
        openAuth();
        setTimeout(() => $("authEmail")?.focus(), 60);
      }
    } catch (_) {
      // Never block the existing FormFit interface because auth is unavailable.
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", showAuthOnFirstLoad, {once:true});
  } else {
    showAuthOnFirstLoad();
  }
  $("authClose")?.addEventListener("click", closeAuth);
  $("historyClose")?.addEventListener("click", () => $("historyDrawer").classList.remove("open"));
  $("authForm")?.addEventListener("submit", submitAuth);
  $("authSwitch")?.addEventListener("click", () => {
    registerMode = !registerMode;
    $("authTitle").textContent = registerMode ? "Create account" : "Sign in";
    $("authSubmit").textContent = registerMode ? "Create account" : "Sign in";
    $("authPassword").setAttribute("autocomplete", registerMode ? "new-password" : "current-password");
    $("authSwitch").textContent = registerMode ? "Already have an account? Sign in" : "Create an account";
    setMessage("");
  });
})();
