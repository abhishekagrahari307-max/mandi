import { APPS, CATEGORIES } from "./catalog.js";

const state = {
  lang: localStorage.getItem("craft_lang") || "en",
  theme: localStorage.getItem("craft_theme") || "dark",
  category: "all",
  query: "",
  releases: {},
  cardShotIdx: {},
  openTabs: [],       // [{ id, renderer: "" | "?webgl" | "?cpu" }]
  activeTab: null,    // app id
  splitTab: null,     // optional second app id for side-by-side split screen
  studioVisible: false,
  topbarCollapsed: false,
  keybarOpen: window.matchMedia("(max-width: 900px)").matches,
  modalApp: null,
  modalShotIdx: 0,
  deferredPrompt: null
};

const byId = (id) => APPS.find((a) => a.id === id || a.alias === id);
const el = (id) => document.getElementById(id);

function detectVisitorOS() {
  const ua = navigator.userAgent.toLowerCase();
  if (ua.includes("win")) return "windows";
  if (ua.includes("mac")) return "macos";
  if (ua.includes("linux")) return "linux";
  return "web";
}

function appVersion(app) {
  return state.releases[app.id]?.tag || app.defaultVersion;
}

function appSizeMb(app) {
  const bytes = state.releases[app.id]?.web_bytes;
  return bytes ? (bytes / 1048576).toFixed(1) : app.defaultSizeMb.toFixed(1);
}

function applyTheme() {
  document.documentElement.setAttribute("data-theme", state.theme);
  localStorage.setItem("craft_theme", state.theme);
  const btn = el("themeBtn");
  if (btn) btn.textContent = state.theme === "dark" ? "☀ Light" : "☾ Dark";
}

function applyLang() {
  localStorage.setItem("craft_lang", state.lang);
  const hi = state.lang === "hi";
  el("langBtn").textContent = hi ? "English" : "हिंदी";
  el("heroEyebrow").textContent = hi
    ? "14 PURE RUST + WEBASSEMBLY ऐप्स · 100% मुफ़्त और ऑफ़लाइन-रेडी"
    : "14 PURE RUST + WEBASSEMBLY APPS · ZERO CLOUD UPLOAD · MIT / APACHE-2.0";
  el("heroTitle").textContent = hi
    ? "Excel, Photo, PDF और पूरा Creative व Office Suite — सीधे आपके ब्राउज़र में"
    : "Excel, Photo, PDF & Complete Pro Suite — Live in Your Browser";
  el("heroSub").textContent = hi
    ? "GridCraft (Excel .xlsx), PhotoCraft (Photoshop .psd), PdfCraft (PDF एडिटर), WordCraft (.docx), DeckCraft (.pptx), Vector, Video, Audio, UI और CAD — सब एक ही वेबसाइट पर बिना साइन-अप चलाएँ।"
    : "Run GridCraft (Excel .xlsx), PhotoCraft (Photoshop .psd), PdfCraft (PDF Workbench), Word, Slides, Vector, Video, VFX, Audio DAW, UI & DWG CAD instantly in WebAssembly — or download native apps.";
  el("sectionHeading").textContent = hi
    ? "सभी 14 सुइट ऐप्स (Excel, Photo, PDF और अन्य)"
    : "Complete 14-App Suite (Excel, Photo, PDF & All Crafting Tools)";
  el("searchInput").placeholder = hi
    ? "खोजें: Excel, Photo, PDF, Word, PSD, XLSX, Video, CAD..."
    : "Search apps or formats: Excel, Photo, PDF, PSD, XLSX, DOCX, Video, CAD...";
  renderFilters();
  renderSpotlight();
  renderSuiteGrid();
}

function renderSpotlight() {
  const hi = state.lang === "hi";
  const featured = APPS.filter((a) => a.featuredPriority > 0).sort(
    (a, b) => a.featuredPriority - b.featuredPriority
  );
  const wrap = el("spotlightGrid");
  wrap.innerHTML = featured
    .map((app) => {
      const ink = state.theme === "dark" ? app.inkDark : app.inkLight;
      return `
      <article class="spotlight-card" style="--app-color:${app.color};--app-ink:${ink}">
        <div class="spotlight-shot" data-open-studio="${app.id}" title="Launch ${app.name} in Browser">
          <img src="${app.shots[0].src}" alt="${app.name} screenshot" loading="eager">
          <span class="spotlight-badge">${app.priorityBadge}</span>
          <span class="spotlight-ver">${appVersion(app)} · ${appSizeMb(app)} MB WASM</span>
        </div>
        <div class="spotlight-body">
          <div class="app-head">
            <img class="app-icon" src="${app.icon}" alt="${app.name} icon">
            <div>
              <h2 class="app-name">${app.name}</h2>
              <p class="app-role">${hi ? app.roleHi : app.role}</p>
            </div>
          </div>
          <p class="app-desc">${hi ? app.headlineHi : app.headline}</p>
          <div class="format-row">
            ${app.formats.map((f) => `<span class="fmt-tag">${f}</span>`).join("")}
          </div>
          <div class="card-actions">
            <button class="btn-launch" data-open-studio="${app.id}">
              ▶ ${hi ? "ब्राउज़र में चलाएँ" : `Open ${app.alias.toUpperCase()} App`}
            </button>
            <a class="btn-ghost" href="${app.appPath}" target="_blank" rel="noopener" title="Open standalone tab">↗</a>
            <button class="btn-ghost" data-open-details="${app.id}">
              ${hi ? "स्क्रीनशॉट / डाउनलोड" : "Details"}
            </button>
          </div>
        </div>
      </article>`;
    })
    .join("");
}

function renderFilters() {
  const hi = state.lang === "hi";
  const bar = el("filterTabs");
  bar.innerHTML = CATEGORIES.map((cat) => {
    const count =
      cat.id === "all" ? APPS.length : APPS.filter((a) => a.category === cat.id).length;
    return `<button class="filter-tab ${state.category === cat.id ? "active" : ""}" data-cat="${cat.id}">
      ${hi ? cat.labelHi : cat.label} (${count})
    </button>`;
  }).join("");
}

function filteredApps() {
  const q = state.query.trim().toLowerCase();
  return APPS.filter((app) => {
    if (state.category !== "all" && app.category !== state.category) return false;
    if (!q) return true;
    const hay = [
      app.id,
      app.alias,
      app.name,
      app.role,
      app.roleHi,
      app.headline,
      app.headlineHi,
      app.about,
      ...app.formats,
      ...app.keywords
    ]
      .join(" ")
      .toLowerCase();
    return hay.includes(q);
  });
}

function renderSuiteGrid() {
  const hi = state.lang === "hi";
  const list = filteredApps();
  const grid = el("suiteGrid");
  if (!list.length) {
    grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1">
      <p>${hi ? "कोई ऐप नहीं मिला — खोज साफ़ करें।" : "No matching apps found — clear search filter."}</p>
    </div>`;
    return;
  }
  grid.innerHTML = list
    .map((app) => {
      const ink = state.theme === "dark" ? app.inkDark : app.inkLight;
      const idx = state.cardShotIdx[app.id] || 0;
      const shot = app.shots[idx] || app.shots[0];
      return `
      <article class="suite-card" style="--app-color:${app.color};--app-ink:${ink}">
        <div class="suite-thumb" data-open-studio="${app.id}">
          <img id="shot-${app.id}" src="${shot.src}" alt="${app.name} — ${shot.caption}" loading="lazy">
          <span class="spotlight-ver">${appVersion(app)} · ${appSizeMb(app)} MB</span>
          ${
            app.shots.length > 1
              ? `<div class="shot-dots" data-stop-prop="1">
                  ${app.shots
                    .map(
                      (_, i) =>
                        `<button class="shot-dot ${i === idx ? "active" : ""}" data-shot-card="${app.id}" data-shot-i="${i}" aria-label="Preview ${i + 1}"></button>`
                    )
                    .join("")}
                </div>`
              : ""
          }
        </div>
        <div class="suite-body">
          <div class="app-head">
            <img class="app-icon" src="${app.icon}" alt="${app.name}">
            <div>
              <h3 class="app-name">${app.name}</h3>
              <p class="app-role">${hi ? app.roleHi : app.role}</p>
            </div>
          </div>
          <p class="app-desc">${hi ? app.headlineHi : app.headline}</p>
          <div class="format-row">
            ${app.formats.slice(0, 5).map((f) => `<span class="fmt-tag">${f}</span>`).join("")}
          </div>
          <div class="card-actions">
            <button class="btn-launch" data-open-studio="${app.id}">
              ▶ ${hi ? "खोलें (Web)" : "Launch Web App"}
            </button>
            <a class="btn-ghost" href="${app.appPath}" target="_blank" rel="noopener" title="Standalone Full Tab">↗</a>
            <button class="btn-ghost" data-open-details="${app.id}" title="Screenshots & Desktop Downloads">⬇</button>
          </div>
        </div>
      </article>`;
    })
    .join("");
}

/* =========================================================
   PERSISTENT MULTI-TAB + SPLIT-VIEW WEBASSEMBLY STUDIO OS
   ========================================================= */
function ensureIframeSlot(appId, rendererQuery = "") {
  const app = byId(appId);
  if (!app) return null;
  let slot = document.getElementById(`frame-slot-${app.id}`);
  const targetSrc = `${app.appPath}${rendererQuery}`;
  if (!slot) {
    slot = document.createElement("div");
    slot.className = "app-frame-slot";
    slot.id = `frame-slot-${app.id}`;
    const iframe = document.createElement("iframe");
    iframe.src = targetSrc;
    iframe.title = `${app.name} WebAssembly Studio`;
    iframe.allow = "fullscreen; clipboard-read; clipboard-write";
    iframe.setAttribute("allowfullscreen", "true");
    slot.appendChild(iframe);
    el("studioStage").appendChild(slot);
  } else {
    const iframe = slot.querySelector("iframe");
    if (iframe && iframe.dataset.renderer !== rendererQuery) {
      iframe.src = targetSrc;
    }
  }
  slot.querySelector("iframe").dataset.renderer = rendererQuery;
  return slot;
}

export function openStudio(appId, updateHash = true) {
  const app = byId(appId);
  if (!app) return;
  let tab = state.openTabs.find((t) => t.id === app.id);
  if (!tab) {
    tab = { id: app.id, renderer: "" };
    state.openTabs.push(tab);
  }
  state.activeTab = app.id;
  if (state.splitTab === app.id) state.splitTab = null;
  state.studioVisible = true;
  ensureIframeSlot(app.id, tab.renderer);
  syncStudioDOM();
  if (updateHash) history.replaceState(null, "", `#studio/${app.id}`);
}

function closeStudioTab(appId) {
  state.openTabs = state.openTabs.filter((t) => t.id !== appId);
  const slot = document.getElementById(`frame-slot-${appId}`);
  if (slot) slot.remove();
  if (state.splitTab === appId) state.splitTab = null;
  if (state.activeTab === appId) {
    state.activeTab = state.openTabs.length ? state.openTabs[state.openTabs.length - 1].id : null;
  }
  if (!state.activeTab) {
    minimizeStudio();
    return;
  }
  syncStudioDOM();
  history.replaceState(null, "", `#studio/${state.activeTab}`);
}

function minimizeStudio() {
  state.studioVisible = false;
  syncStudioDOM();
  history.replaceState(null, "", window.location.pathname + window.location.search);
}

function syncStudioDOM() {
  const shell = el("studioShell");
  const resumeBtn = el("resumeStudioBtn");
  document.body.classList.toggle("studio-open", state.studioVisible);
  shell.hidden = !state.studioVisible;
  shell.classList.toggle("topbar-collapsed", state.topbarCollapsed);
  el("touchKeybar").hidden = !state.keybarOpen;
  el("toggleKeysBtn").classList.toggle("active", state.keybarOpen);

  if (state.openTabs.length > 0 && !state.studioVisible) {
    resumeBtn.hidden = false;
    resumeBtn.innerHTML = `<span class="pulse-dot"></span> Studio (${state.openTabs.length} open)`;
  } else {
    resumeBtn.hidden = true;
  }

  if (!state.studioVisible) return;

  // Render open tabs
  el("studioTabs").innerHTML = state.openTabs
    .map((t) => {
      const app = byId(t.id);
      const isAct = t.id === state.activeTab || t.id === state.splitTab;
      return `<div class="studio-tab ${isAct ? "active" : ""}" data-switch-tab="${app.id}">
        <img src="${app.icon}" alt="">
        <span>${app.name}</span>
        <button class="studio-tab-close" data-close-tab="${app.id}" title="Close ${app.name}">×</button>
      </div>`;
    })
    .join("");

  // Populate quick-open & split selects
  el("quickOpenSelect").innerHTML =
    `<option value="">+ Open App</option>` +
    APPS.map((a) => `<option value="${a.id}">${a.name} (${a.alias.toUpperCase()})</option>`).join("");

  el("splitAppSelect").innerHTML =
    `<option value="">◫ Single View</option>` +
    APPS.filter((a) => a.id !== state.activeTab)
      .map(
        (a) =>
          `<option value="${a.id}" ${state.splitTab === a.id ? "selected" : ""}>Split: + ${a.name}</option>`
      )
      .join("");

  const activeObj = state.openTabs.find((t) => t.id === state.activeTab);
  if (activeObj) {
    el("rendererSelect").value = activeObj.renderer;
    const activeApp = byId(activeObj.id);
    el("standaloneLink").href = `${activeApp.appPath}${activeObj.renderer}`;
  }

  // Toggle frame visibility without unmounting inactive WASM instances
  const stage = el("studioStage");
  stage.classList.toggle("split-active", Boolean(state.splitTab));
  for (const child of stage.children) {
    const id = child.id.replace("frame-slot-", "");
    child.hidden = id !== state.activeTab && id !== state.splitTab;
  }
}

function sendShortcutToActiveFrame(key, { ctrl = false, shift = false } = {}) {
  const slot = document.getElementById(`frame-slot-${state.activeTab}`);
  const win = slot?.querySelector("iframe")?.contentWindow;
  if (!win) return;
  try {
    win.focus();
    const init = {
      key,
      code: key.length === 1 ? `Key${key.toUpperCase()}` : key,
      ctrlKey: ctrl,
      metaKey: ctrl && navigator.platform.includes("Mac"),
      shiftKey: shift,
      bubbles: true,
      cancelable: true
    };
    win.document.dispatchEvent(new KeyboardEvent("keydown", init));
    win.document.dispatchEvent(new KeyboardEvent("keyup", init));
  } catch (_) {
    /* cross-origin fallback ignored; all apps are same-origin */
  }
}

/* =========================================================
   APP DETAILS & NATIVE DESKTOP INSTALLERS MODAL
   ========================================================= */
function openDetailsModal(appId) {
  const app = byId(appId);
  if (!app) return;
  state.modalApp = app;
  state.modalShotIdx = 0;
  renderDetailsModal();
  el("detailsModal").hidden = false;
}

function renderDetailsModal() {
  const app = state.modalApp;
  if (!app) return;
  const hi = state.lang === "hi";
  const shot = app.shots[state.modalShotIdx] || app.shots[0];
  const rel = state.releases[app.id] || {};
  const dls = rel.downloads || {};
  const os = detectVisitorOS();
  const releasePage = rel.html_url || `https://github.com/${app.repo}/releases/latest`;

  const dlItems = [
    { key: "windows_msi", label: "Windows Installer (.msi)", match: os === "windows" },
    { key: "windows_zip", label: "Windows Portable (.zip)", match: false },
    { key: "macos_dmg", label: "macOS Universal (.dmg)", match: os === "macos" },
    { key: "linux_appimage", label: "Linux AppImage", match: os === "linux" },
    { key: "linux_deb", label: "Debian / Ubuntu (.deb)", match: false },
    { key: "linux_flatpak", label: "Linux Flatpak", match: false },
    { key: "web_zip", label: "Offline Web Bundle (.zip)", match: false }
  ].filter((item) => dls[item.key]);

  el("modalBody").innerHTML = `
    <div class="modal-top">
      <div class="app-head">
        <img class="app-icon" src="${app.icon}" alt="${app.name}" style="width:52px;height:52px">
        <div>
          <h2 class="app-name" style="font-size:22px">${app.name} <span style="font-weight:500;font-size:14px;color:var(--ink-muted)">${appVersion(app)}</span></h2>
          <p class="app-role">${hi ? app.roleHi : app.role}</p>
        </div>
      </div>
      <div style="display:flex;gap:8px;align-items:center">
        <button class="btn-launch" style="--app-color:${app.color};padding:0 16px" data-modal-launch="${app.id}">
          ▶ ${hi ? "ब्राउज़र में चलाएँ" : "Launch in Browser"}
        </button>
        <button class="btn-ghost" id="closeModalBtn">✕</button>
      </div>
    </div>

    <div class="modal-gallery">
      <img src="${shot.src}" alt="${shot.caption}">
    </div>
    <div class="modal-caption-bar">
      <span>${shot.caption}</span>
      <div class="modal-thumbs">
        ${app.shots
          .map(
            (_, i) =>
              `<button class="modal-thumb-btn ${i === state.modalShotIdx ? "active" : ""}" data-modal-shot="${i}">${i + 1}</button>`
          )
          .join("")}
      </div>
    </div>

    <p style="margin:0 0 12px;color:var(--ink-soft);font-size:14px;line-height:1.55">${app.about}</p>
    <div class="format-row">
      ${app.formats.map((f) => `<span class="fmt-tag">${f}</span>`).join("")}
    </div>

    <div class="feature-grid">
      ${app.features
        .map(([t, d]) => `<div class="feature-box"><h4>${t}</h4><p>${d}</p></div>`)
        .join("")}
    </div>

    <div class="downloads-box">
      <strong style="font-size:13.5px">${hi ? "नेटिव डेस्कटॉप और ऑफ़लाइन डाउनलोड" : "Native Desktop Installers & Source Code"}</strong>
      <div class="dl-buttons">
        ${dlItems
          .map(
            (i) =>
              `<a class="dl-link ${i.match ? "recommended" : ""}" href="${dls[i.key]}" target="_blank" rel="noopener">⬇ ${i.label}</a>`
          )
          .join("")}
        <a class="dl-link" href="${releasePage}" target="_blank" rel="noopener">All Releases (${appVersion(app)}) ↗</a>
        <a class="dl-link" href="https://github.com/${app.repo}" target="_blank" rel="noopener">GitHub Source (${app.repo}) ↗</a>
      </div>
    </div>
  `;
}

/* =========================================================
   EVENT WIRING & INITIALIZATION
   ========================================================= */
function bindEvents() {
  document.addEventListener("click", (e) => {
    if (e.target.closest("[data-stop-prop]")) e.stopPropagation();

    const shotBtn = e.target.closest("[data-shot-card]");
    if (shotBtn) {
      e.stopPropagation();
      const id = shotBtn.dataset.shotCard;
      const i = Number(shotBtn.dataset.shotI);
      state.cardShotIdx[id] = i;
      renderSuiteGrid();
      return;
    }

    const studioBtn = e.target.closest("[data-open-studio]");
    if (studioBtn) {
      openStudio(studioBtn.dataset.openStudio);
      return;
    }

    const detailsBtn = e.target.closest("[data-open-details]");
    if (detailsBtn) {
      openDetailsModal(detailsBtn.dataset.openDetails);
      return;
    }

    const catBtn = e.target.closest("[data-cat]");
    if (catBtn) {
      state.category = catBtn.dataset.cat;
      renderFilters();
      renderSuiteGrid();
      return;
    }

    const closeTabBtn = e.target.closest("[data-close-tab]");
    if (closeTabBtn) {
      e.stopPropagation();
      closeStudioTab(closeTabBtn.dataset.closeTab);
      return;
    }

    const switchTabBtn = e.target.closest("[data-switch-tab]");
    if (switchTabBtn) {
      openStudio(switchTabBtn.dataset.switchTab);
      return;
    }

    const modalShot = e.target.closest("[data-modal-shot]");
    if (modalShot) {
      state.modalShotIdx = Number(modalShot.dataset.modalShot);
      renderDetailsModal();
      return;
    }

    const modalLaunch = e.target.closest("[data-modal-launch]");
    if (modalLaunch) {
      el("detailsModal").hidden = true;
      openStudio(modalLaunch.dataset.modalLaunch);
      return;
    }

    if (e.target.id === "closeModalBtn" || e.target.id === "detailsModal") {
      el("detailsModal").hidden = true;
    }

    const keyAct = e.target.closest("[data-key-cmd]");
    if (keyAct) {
      const cmd = keyAct.dataset.keyCmd;
      if (cmd === "undo") sendShortcutToActiveFrame("z", { ctrl: true });
      else if (cmd === "redo") sendShortcutToActiveFrame("z", { ctrl: true, shift: true });
      else if (cmd === "open") sendShortcutToActiveFrame("o", { ctrl: true });
      else if (cmd === "save") sendShortcutToActiveFrame("s", { ctrl: true });
      else if (cmd === "zoomin") sendShortcutToActiveFrame("=", { ctrl: true });
      else if (cmd === "zoomout") sendShortcutToActiveFrame("-", { ctrl: true });
      else if (cmd === "esc") sendShortcutToActiveFrame("Escape");
    }
  });

  el("searchInput").addEventListener("input", (e) => {
    state.query = e.target.value;
    renderSuiteGrid();
  });

  window.addEventListener("keydown", (e) => {
    if ((e.key === "/" || ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k")) && !state.studioVisible) {
      if (document.activeElement !== el("searchInput")) {
        e.preventDefault();
        el("searchInput").focus();
      }
    }
    if (e.key === "Escape" && !el("detailsModal").hidden) {
      el("detailsModal").hidden = true;
    }
  });

  el("themeBtn").addEventListener("click", () => {
    state.theme = state.theme === "dark" ? "light" : "dark";
    applyTheme();
    renderSpotlight();
    renderSuiteGrid();
  });

  el("langBtn").addEventListener("click", () => {
    state.lang = state.lang === "en" ? "hi" : "en";
    applyLang();
  });

  el("brandHomeBtn").addEventListener("click", () => {
    state.category = "all";
    state.query = "";
    el("searchInput").value = "";
    renderFilters();
    renderSuiteGrid();
    window.scrollTo({ top: 0, behavior: "smooth" });
  });

  el("studioBackBtn").addEventListener("click", minimizeStudio);
  el("resumeStudioBtn").addEventListener("click", () => {
    state.studioVisible = true;
    syncStudioDOM();
  });

  el("quickOpenSelect").addEventListener("change", (e) => {
    if (e.target.value) openStudio(e.target.value);
  });

  el("splitAppSelect").addEventListener("change", (e) => {
    const secondId = e.target.value || null;
    state.splitTab = secondId;
    if (secondId) {
      if (!state.openTabs.find((t) => t.id === secondId)) {
        state.openTabs.push({ id: secondId, renderer: "" });
      }
      ensureIframeSlot(secondId, "");
    }
    syncStudioDOM();
  });

  el("rendererSelect").addEventListener("change", (e) => {
    const activeObj = state.openTabs.find((t) => t.id === state.activeTab);
    if (!activeObj) return;
    activeObj.renderer = e.target.value;
    ensureIframeSlot(activeObj.id, activeObj.renderer);
    syncStudioDOM();
  });

  el("reloadAppBtn").addEventListener("click", () => {
    const slot = document.getElementById(`frame-slot-${state.activeTab}`);
    const iframe = slot?.querySelector("iframe");
    if (iframe) iframe.src = iframe.src;
  });

  el("toggleKeysBtn").addEventListener("click", () => {
    state.keybarOpen = !state.keybarOpen;
    syncStudioDOM();
  });

  el("collapseBarBtn").addEventListener("click", () => {
    state.topbarCollapsed = true;
    syncStudioDOM();
  });

  el("expandBarBtn").addEventListener("click", () => {
    state.topbarCollapsed = false;
    syncStudioDOM();
  });

  el("fullscreenBtn").addEventListener("click", () => {
    if (!document.fullscreenElement) el("studioShell").requestFullscreen?.();
    else document.exitFullscreen?.();
  });

  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    state.deferredPrompt = e;
    el("pwaInstallBtn").hidden = false;
  });

  el("pwaInstallBtn").addEventListener("click", async () => {
    if (!state.deferredPrompt) return;
    state.deferredPrompt.prompt();
    await state.deferredPrompt.userChoice;
    state.deferredPrompt = null;
    el("pwaInstallBtn").hidden = true;
  });

  window.addEventListener("hashchange", handleRoute);
}

function handleRoute() {
  const hash = location.hash.replace(/^#\/?/, "");
  if (!hash) return;
  if (hash.startsWith("studio/") || hash.startsWith("app/")) {
    const id = hash.split("/")[1];
    if (byId(id)) openStudio(id, false);
    return;
  }
  if (hash.startsWith("details/")) {
    const id = hash.split("/")[1];
    if (byId(id)) openDetailsModal(id);
    return;
  }
  if (byId(hash)) {
    openStudio(hash, false);
  }
}

async function init() {
  applyTheme();
  bindEvents();
  applyLang();

  try {
    const res = await fetch("./assets/releases.json", { cache: "no-cache" });
    if (res.ok) {
      state.releases = await res.json();
      renderSpotlight();
      renderSuiteGrid();
    }
  } catch (_) {
    /* Static preview without releases.json uses built-in version metadata */
  }

  handleRoute();
}

init();
