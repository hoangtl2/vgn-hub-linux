(() => {
  "use strict";

  const POLLING_HEIGHTS = {
    125: 28,
    250: 38,
    500: 48,
    1000: 58,
    2000: 68,
    4000: 80,
    8000: 94,
  };

  const DEBOUNCE_OPTIONS = [1, 2, 3, 4, 8, 15, 20];
  const SLEEP_OPTIONS = [
    { sec: 10, label: "10s" },
    { sec: 30, label: "30s" },
    { sec: 60, label: "1m" },
    { sec: 120, label: "2m" },
    { sec: 300, label: "5m" },
    { sec: 600, label: "10m" },
  ];

  // Browser KeyboardEvent.code -> USB HID Usage ID
  const CODE_TO_HID = (() => {
    const m = {};
    for (let i = 0; i < 26; i++) {
      m["Key" + String.fromCharCode(65 + i)] = 0x04 + i;
    }
    const digits = [1, 2, 3, 4, 5, 6, 7, 8, 9, 0];
    digits.forEach((d, idx) => {
      m["Digit" + d] = 0x1e + idx;
    });
    for (let f = 1; f <= 12; f++) m["F" + f] = 0x3a + (f - 1);
    Object.assign(m, {
      Enter: 0x28, Escape: 0x29, Backspace: 0x2a, Tab: 0x2b, Space: 0x2c,
      Minus: 0x2d, Equal: 0x2e, BracketLeft: 0x2f, BracketRight: 0x30, Backslash: 0x31,
      Semicolon: 0x33, Quote: 0x34, Backquote: 0x35, Comma: 0x36, Period: 0x37, Slash: 0x38,
      CapsLock: 0x39, PrintScreen: 0x46, ScrollLock: 0x47, Pause: 0x48,
      Insert: 0x49, Home: 0x4a, PageUp: 0x4b, Delete: 0x4c, End: 0x4d, PageDown: 0x4e,
      ArrowRight: 0x4f, ArrowLeft: 0x50, ArrowDown: 0x51, ArrowUp: 0x52,
      NumLock: 0x53, NumpadDivide: 0x54, NumpadMultiply: 0x55, NumpadSubtract: 0x56,
      NumpadAdd: 0x57, NumpadEnter: 0x58,
      Numpad1: 0x59, Numpad2: 0x5a, Numpad3: 0x5b, Numpad4: 0x5c, Numpad5: 0x5d,
      Numpad6: 0x5e, Numpad7: 0x5f, Numpad8: 0x60, Numpad9: 0x61, Numpad0: 0x62,
      NumpadDecimal: 0x63, ContextMenu: 0x65,
      ControlLeft: 224, ShiftLeft: 225, AltLeft: 226, MetaLeft: 227,
      ControlRight: 228, ShiftRight: 229, AltRight: 230, MetaRight: 231,
    });
    return m;
  })();

  const store = {
    connected: false,
    error: "",
    state: null,
    config: { lang: "vi", theme: "glass", macros: [] },
    catalog: { actions: [], hid_keys: [], supported_models: [], udev_rule_installed: true },
    page: "keys",
    selectedSlot: 0,
    keyTab: "system",
    keySearch: "",
    comboKeys: [],
    macroLoop: 2,
    selectedMacroForBind: 0,
    selectedMacroSlot: 0,
    isRecording: false,
    lastRecTime: 0,
    xySplit: false,
  };

  let nextReqId = 1;
  let rotCommitTimer = null;
  const pending = new Map();

  function rpc(action, params = {}) {
    return new Promise((resolve, reject) => {
      const id = nextReqId++;
      pending.set(id, { resolve, reject });
      const msg = JSON.stringify({ id, action, params });
      if (window.webkit?.messageHandlers?.vgn) {
        window.webkit.messageHandlers.vgn.postMessage(msg);
      } else {
        pending.delete(id);
        reject(new Error("WebKit bridge unavailable"));
      }
    });
  }

  window.__vgnResolve = (id, payload) => {
    const entry = pending.get(id);
    if (!entry) return;
    pending.delete(id);
    if (payload.ok) entry.resolve(payload.data);
    else entry.reject(new Error(payload.error || "Unknown error"));
  };

  window.__vgnEvent = (name, data) => {
    if (!store.state) return;
    if (name === "dpi_changed" && typeof data.active_dpi === "number") {
      store.state.active_dpi = data.active_dpi;
      renderAll();
    } else if (name === "battery") {
      if (typeof data.battery === "number") store.state.battery = data.battery;
      if (typeof data.is_sleep === "boolean") store.state.is_sleep = data.is_sleep;
      renderChrome();
    }
  };

  function tr() {
    return window.VGN_I18N[store.config.lang] || window.VGN_I18N.vi;
  }

  function escHtml(str) {
    return String(str ?? "")
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function hidLabel(code) {
    const found = store.catalog.hid_keys.find((k) => k.code === code);
    return found ? found.label : `0x${code.toString(16)}`;
  }

  function showToast(msg, isErr = false) {
    const box = document.getElementById("toast-container");
    const el = document.createElement("div");
    el.className = `toast ${isErr ? "is-err" : ""}`;
    el.textContent = msg;
    box.appendChild(el);
    setTimeout(() => el.remove(), 2600);
  }

  function openConfirm(title, body, onConfirm) {
    const backdrop = document.getElementById("modal-backdrop");
    document.getElementById("modal-title").textContent = title;
    document.getElementById("modal-body").textContent = body;
    const cancelBtn = document.getElementById("modal-cancel");
    const okBtn = document.getElementById("modal-confirm");
    cancelBtn.textContent = tr().cancel;
    okBtn.textContent = tr().confirm;
    backdrop.hidden = false;
    const close = () => { backdrop.hidden = true; };
    cancelBtn.onclick = close;
    okBtn.onclick = () => {
      close();
      onConfirm();
    };
  }

  async function mutate(action, params = {}, quiet = false) {
    try {
      const res = await rpc(action, params);
      if (res && res.state) {
        store.state = res.state;
        renderAll();
      }
      if (!quiet) showToast(tr().saved);
      return res;
    } catch (err) {
      showToast(tr().errorPrefix + err.message, true);
      throw err;
    }
  }

  function navIcon(id) {
    const icons = {
      keys: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="6" y="2" width="12" height="20" rx="6"/><line x1="12" y1="6" x2="12" y2="10"/></svg>`,
      dpi: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/></svg>`,
      performance: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>`,
      macros: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>`,
      rotation: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/></svg>`,
      params: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/></svg>`,
      system: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>`,
    };
    return icons[id] || "";
  }

  function formatSleep(sec) {
    return sec >= 60 && sec % 60 === 0 ? `${sec / 60}m` : `${sec}s`;
  }

  function activeLedColor() {
    if (!store.state || !store.state.dpi_stages.length) return "#ffff00";
    const st = store.state.dpi_stages[store.state.active_dpi] || store.state.dpi_stages[0];
    return st.color || "#ffff00";
  }

  function renderChrome() {
    const t = tr();
    document.body.className = store.config.theme === "solid" ? "theme-solid" : "theme-glass";
    document.getElementById("btn-theme").textContent = store.config.theme === "solid" ? "Solid" : "Glass";
    document.getElementById("btn-lang").textContent = store.config.lang.toUpperCase();
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const k = el.getAttribute("data-i18n");
      if (t[k]) el.textContent = t[k];
    });

    const connPill = document.getElementById("conn-pill");
    const batPill = document.getElementById("battery-pill");
    const demoBtn = document.getElementById("btn-demo-toggle");

    if (store.connected && store.state) {
      const s = store.state;
      const modeText = s.is_demo ? t.demoMode : (s.is_wireless ? t.wirelessMode : t.wiredMode);
      connPill.className = `pill ${s.is_demo ? "pill-demo" : "pill-ok"}`;
      connPill.textContent = modeText;
      batPill.hidden = false;
      batPill.textContent = s.is_sleep ? `${t.sleeping} · ${s.battery}%` : `${s.battery}%`;

      document.getElementById("sidebar-device-name").textContent = s.device_name;
      document.getElementById("sidebar-bat").textContent = `${s.battery}%`;
      document.getElementById("sidebar-mode").textContent = modeText;
      document.getElementById("sidebar-fw").textContent =
        `fw v${s.firmware} · ${s.sensor}` + (s.dongle_firmware ? ` · RX v${s.dongle_firmware}` : "");
      document.getElementById("sidebar-thumb").innerHTML = window.VgnMouseSvg.renderTop({
        ledColor: activeLedColor(),
        compact: true,
      });
      demoBtn.textContent = s.is_demo ? t.connectReal : t.tryDemo;
    } else {
      connPill.className = "pill pill-err";
      connPill.textContent = t.disconnectedTitle;
      batPill.hidden = true;
      document.getElementById("sidebar-device-name").textContent = "Dragonfly 3 Ultra";
      document.getElementById("sidebar-bat").textContent = "--";
      document.getElementById("sidebar-mode").textContent = "Offline";
      document.getElementById("sidebar-fw").textContent = "391d:1028 / 1a25";
      document.getElementById("sidebar-thumb").innerHTML = window.VgnMouseSvg.renderTop({ compact: true });
      demoBtn.textContent = t.tryDemo;
    }

    // Left Nav
    const navList = document.getElementById("nav-list");
    const pages = ["keys", "dpi", "performance", "macros", "rotation", "params", "system"];
    navList.innerHTML = pages
      .map(
        (id) => `
      <button class="nav-item ${store.page === id ? "is-active" : ""}" data-page="${id}">
        ${navIcon(id)}
        <span>${t.nav[id]}</span>
      </button>`
      )
      .join("");
    navList.querySelectorAll("[data-page]").forEach((btn) => {
      btn.onclick = () => {
        store.page = btn.getAttribute("data-page");
        renderChrome();
        renderStage();
      };
    });

    // Right Profile list & Telemetry
    const profList = document.getElementById("profile-list");
    const telGrid = document.getElementById("telemetry-grid");
    if (store.connected && store.state) {
      const s = store.state;
      profList.innerHTML = Array.from({ length: s.profile_count }, (_, i) => `
        <button class="profile-btn ${s.profile === i ? "is-active" : ""}" data-profile="${i}">
          <span>${t.profileItem} ${i + 1}</span>
          ${s.profile === i ? `<span class="dot" style="background:${activeLedColor()}"></span>` : ""}
        </button>`).join("");
      profList.querySelectorAll("[data-profile]").forEach((b) => {
        b.onclick = () => mutate("set_profile", { profile: Number(b.dataset.profile) });
      });

      const curDpi = s.dpi_stages[s.active_dpi] || { x: 0, y: 0, color: "#fff" };
      telGrid.innerHTML = `
        <div class="tel-row"><span class="tel-k">${t.tel.activeDpi}</span><span class="tel-v"><span class="dot" style="background:${curDpi.color}"></span>${curDpi.x}</span></div>
        <div class="tel-row"><span class="tel-k">${t.tel.polling}</span><span class="tel-v">${s.polling_hz} Hz</span></div>
        <div class="tel-row"><span class="tel-k">${t.tel.lod}</span><span class="tel-v">${s.lod_mm}</span></div>
        <div class="tel-row"><span class="tel-k">${t.tel.debounce}</span><span class="tel-v">${s.debounce_ms} ms</span></div>
        <div class="tel-row"><span class="tel-k">${t.tel.sleep}</span><span class="tel-v">${formatSleep(s.sleep_seconds)}</span></div>
        <div class="tel-row"><span class="tel-k">${t.tel.rotation}</span><span class="tel-v">${s.sensor_rotation}°</span></div>
        <div class="tel-row"><span class="tel-k">${t.tel.fps}</span><span class="tel-v">${s.fps_mode === 1 ? "20K FPS" : "Basic"}</span></div>
      `;
    } else {
      profList.innerHTML = `<div style="color:var(--text-dim);font-size:12px;">--</div>`;
      telGrid.innerHTML = `<div style="color:var(--text-dim);font-size:12px;">--</div>`;
    }
  }

  function renderDisconnected() {
    const t = tr();
    const stage = document.getElementById("main-stage");
    stage.innerHTML = `
      <div class="empty-state card">
        ${window.VgnMouseSvg.renderTop({ compact: false })}
        <h2>${t.disconnectedTitle}</h2>
        <p style="color:var(--text-muted);max-width:440px;">${store.error || t.disconnectedDesc}</p>
        <div style="display:flex;gap:10px;margin-top:8px;">
          <button id="empty-retry" class="btn-primary">${t.retryBtn}</button>
          <button id="empty-demo" class="btn-secondary">${t.tryDemo}</button>
        </div>
      </div>
    `;
    document.getElementById("empty-retry").onclick = boot;
    document.getElementById("empty-demo").onclick = async () => {
      const res = await rpc("enter_demo");
      applyBundle(res);
    };
  }

  function renderKeysPage() {
    const t = tr();
    const s = store.state;
    const lang = store.config.lang;
    const stage = document.getElementById("main-stage");
    const activeBtn = s.buttons[store.selectedSlot] || s.buttons[0];

    const calloutsHtml = s.buttons
      .map((b) => {
        const slotName = lang === "vi" ? b.label_vi : b.label_en;
        const actionName = lang === "vi" ? b.action_label_vi : b.action_label_en;
        return `
          <button class="callout-badge callout-slot-${b.slot} ${store.selectedSlot === b.slot ? "is-active" : ""}" data-slot="${b.slot}">
            <div class="callout-name">${slotName}</div>
            <div class="callout-val">${actionName}</div>
          </button>`;
      })
      .join("");

    let paletteBody = "";
    const q = store.keySearch.trim().toLowerCase();
    const actions = store.catalog.actions.filter((a) => {
      if (!q) return true;
      return a.label_en.toLowerCase().includes(q) || a.label_vi.toLowerCase().includes(q) || a.id.includes(q);
    });

    if (store.keyTab === "system") {
      const renderGroup = (title, cats) => {
        const list = actions.filter((a) => cats.includes(a.category));
        if (!list.length) return "";
        return `
          <div class="cat-heading">${title}</div>
          <div class="action-grid">
            ${list
              .map((a) => {
                const lbl = lang === "vi" ? a.label_vi : a.label_en;
                const isCur = activeBtn.action_id === a.id;
                return `<button class="action-tile ${isCur ? "is-current" : ""}" data-act="${a.id}">${lbl}</button>`;
              })
              .join("")}
          </div>`;
      };
      paletteBody =
        renderGroup(t.keybinding.catMouse, ["disable", "mouse"]) +
        renderGroup(t.keybinding.catDpi, ["dpi"]) +
        renderGroup(t.keybinding.catScroll, ["scroll"]);
    } else if (store.keyTab === "media") {
      const renderGroup = (title, cats) => {
        const list = actions.filter((a) => cats.includes(a.category));
        if (!list.length) return "";
        return `
          <div class="cat-heading">${title}</div>
          <div class="action-grid">
            ${list
              .map((a) => {
                const lbl = lang === "vi" ? a.label_vi : a.label_en;
                const isCur = activeBtn.action_id === a.id;
                return `<button class="action-tile ${isCur ? "is-current" : ""}" data-act="${a.id}">${lbl}</button>`;
              })
              .join("")}
          </div>`;
      };
      paletteBody =
        renderGroup(t.keybinding.catMedia, ["media"]) +
        renderGroup(t.keybinding.catSystem, ["system"]);
    } else if (store.keyTab === "keyboard") {
      const comboText = store.comboKeys.map(hidLabel).join(" + ");
      paletteBody = `
        <p class="card-sub">${t.keybinding.comboHint}</p>
        <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
          <input id="combo-capture" class="text-input" style="min-width:260px;" readonly
                 value="${escHtml(comboText)}" placeholder="${t.keybinding.comboPlaceholder}"/>
          <button id="combo-apply" class="btn-primary" ${store.comboKeys.length ? "" : "disabled"}>${t.keybinding.applyCombo}</button>
          <button id="combo-clear" class="btn-secondary">${t.keybinding.clearCombo}</button>
        </div>
      `;
    } else if (store.keyTab === "macros") {
      const macroOptions = store.config.macros
        .map((m) => `<option value="${m.slot}" ${store.selectedMacroForBind === m.slot ? "selected" : ""}>${m.name} (${m.events.length})</option>`)
        .join("");
      paletteBody = `
        <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
          <select id="bind-macro-select" class="select-input">${macroOptions}</select>
          <select id="bind-macro-loop" class="select-input">
            <option value="2" ${store.macroLoop === 2 ? "selected" : ""}>${t.keybinding.macroModeRepeat}</option>
            <option value="1" ${store.macroLoop === 1 ? "selected" : ""}>${t.keybinding.macroModeHold}</option>
          </select>
          <button id="bind-macro-apply" class="btn-primary">${t.keybinding.assignMacro}</button>
        </div>
      `;
    }

    stage.innerHTML = `
      <section class="keybind-hero">
        <div class="keybind-canvas">
          ${window.VgnMouseSvg.renderTop({
            ledColor: activeLedColor(),
            activeSlot: store.selectedSlot,
            interactive: true,
          })}
          ${calloutsHtml}
        </div>
        <button id="btn-restore-default" class="ghost-btn">${t.restoreDefault}</button>
      </section>

      <section class="card">
        <div class="palette-header">
          <div>
            <div class="card-title">${t.keybinding.editingSlot}: <span style="color:#60a5fa">${lang === "vi" ? activeBtn.label_vi : activeBtn.label_en}</span></div>
            <div style="font-size:11.5px;color:var(--text-muted);">${t.keybinding.hint}</div>
          </div>
          <input id="key-search" class="search-input" type="search" value="${escHtml(store.keySearch)}" placeholder="${t.keybinding.searchPlaceholder}" />
        </div>
        <div class="tab-strip" style="margin-bottom:14px;">
          ${["system", "keyboard", "media", "macros"]
            .map((k) => `<button class="tab-btn ${store.keyTab === k ? "is-active" : ""}" data-ktab="${k}">${t.keybinding.tabs[k]}</button>`)
            .join("")}
        </div>
        ${paletteBody}
      </section>
    `;

    stage.querySelectorAll("[data-slot]").forEach((el) => {
      el.onclick = () => {
        store.selectedSlot = Number(el.getAttribute("data-slot"));
        renderKeysPage();
      };
    });

    stage.querySelectorAll("[data-ktab]").forEach((el) => {
      el.onclick = () => {
        store.keyTab = el.getAttribute("data-ktab");
        renderKeysPage();
      };
    });

    const searchInput = document.getElementById("key-search");
    searchInput.oninput = () => {
      store.keySearch = searchInput.value;
      renderKeysPage();
      const refocused = document.getElementById("key-search");
      if (refocused) {
        refocused.focus();
        refocused.setSelectionRange(refocused.value.length, refocused.value.length);
      }
    };

    stage.querySelectorAll("[data-act]").forEach((el) => {
      el.onclick = () =>
        mutate("set_button_binding", {
          slot: store.selectedSlot,
          action_id: el.getAttribute("data-act"),
        });
    });

    const comboCap = document.getElementById("combo-capture");
    if (comboCap) {
      comboCap.onkeydown = (ev) => {
        ev.preventDefault();
        const hid = CODE_TO_HID[ev.code];
        if (!hid) return;
        if (!store.comboKeys.includes(hid) && store.comboKeys.length < 3) {
          store.comboKeys.push(hid);
          renderKeysPage();
          document.getElementById("combo-capture")?.focus();
        }
      };
      document.getElementById("combo-apply").onclick = () =>
        mutate("set_button_binding", { slot: store.selectedSlot, keys: store.comboKeys });
      document.getElementById("combo-clear").onclick = () => {
        store.comboKeys = [];
        renderKeysPage();
      };
    }

    const bindMacroSel = document.getElementById("bind-macro-select");
    if (bindMacroSel) {
      bindMacroSel.onchange = () => { store.selectedMacroForBind = Number(bindMacroSel.value); };
      document.getElementById("bind-macro-loop").onchange = (ev) => {
        store.macroLoop = Number(ev.target.value);
      };
      document.getElementById("bind-macro-apply").onclick = () =>
        mutate("set_button_binding", {
          slot: store.selectedSlot,
          macro_id: store.selectedMacroForBind,
          macro_loop: store.macroLoop,
        });
    }

    document.getElementById("btn-restore-default").onclick = () => {
      openConfirm(t.restoreConfirmTitle, t.restoreConfirmBody, () => mutate("restore_factory"));
    };
  }

  function renderDpiPage() {
    const t = tr();
    const s = store.state;
    const stage = document.getElementById("main-stage");
    const active = s.dpi_stages[s.active_dpi] || s.dpi_stages[0];
    const isSplit = store.xySplit || active.x !== active.y;

    const rowsHtml = s.dpi_stages
      .map(
        (st, idx) => `
      <div class="dpi-stage-row ${idx === s.active_dpi ? "is-active" : ""}" data-dpi-row="${idx}">
        <div class="color-input-wrap" title="${t.dpi.colorLabel}">
          <input type="color" value="${st.color}" data-dpi-color="${idx}"/>
        </div>
        <span class="dpi-stage-name">DPI ${idx + 1}</span>
        <span class="dpi-stage-val">${st.x === st.y ? st.x : `${st.x} / ${st.y}`}</span>
      </div>`
      )
      .join("");

    stage.innerHTML = `
      <section class="dpi-hero">
        ${window.VgnMouseSvg.renderBottom({ ledColor: active.color })}
      </section>

      <div class="dpi-grid">
        <section class="card">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
            <div class="card-title" style="margin:0;">${t.dpi.levels} ${s.dpi_stages.length}/${s.max_dpi_stages}</div>
            <div style="display:flex;gap:6px;">
              <button id="dpi-rem" class="seg-btn" ${s.dpi_stages.length <= 1 ? "disabled" : ""}>-</button>
              <button id="dpi-add" class="seg-btn" ${s.dpi_stages.length >= s.max_dpi_stages ? "disabled" : ""}>+</button>
            </div>
          </div>
          <div class="dpi-stage-list">${rowsHtml}</div>
        </section>

        <section class="card">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;">
            <div>
              <div class="card-title">${t.dpi.settingsTitle} (DPI ${s.active_dpi + 1})</div>
              <div class="card-sub">${t.dpi.settingsSub}</div>
            </div>
            <label style="display:flex;align-items:center;gap:8px;font-size:12px;font-weight:600;">
              <span>${t.dpi.splitXY}</span>
              <span class="switch">
                <input type="checkbox" id="xy-toggle" ${isSplit ? "checked" : ""}/>
                <span class="switch-track"></span>
              </span>
            </label>
          </div>

          <div style="margin-top:8px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
              <span style="font-weight:600;">${isSplit ? t.dpi.axisX : t.dpi.axisXY}</span>
              <input id="dpi-x-num" class="num-input" type="number" min="${s.dpi_min}" max="${s.dpi_max}" step="${s.dpi_step}" value="${active.x}" style="width:100px;text-align:right;font-weight:700;"/>
            </div>
            <input id="dpi-x-slider" class="range-slider" type="range" min="${s.dpi_min}" max="${s.dpi_max}" step="${s.dpi_step}" value="${active.x}"/>
            <div style="display:flex;justify-content:space-between;font-size:10.5px;color:var(--text-dim);margin-top:4px;">
              <span>${s.dpi_min}</span><span>10500</span><span>21000</span><span>31500</span><span>${s.dpi_max}</span>
            </div>
          </div>

          ${
            isSplit
              ? `<div style="margin-top:14px;">
                  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                    <span style="font-weight:600;">${t.dpi.axisY}</span>
                    <input id="dpi-y-num" class="num-input" type="number" min="${s.dpi_min}" max="${s.dpi_max}" step="${s.dpi_step}" value="${active.y}" style="width:100px;text-align:right;font-weight:700;"/>
                  </div>
                  <input id="dpi-y-slider" class="range-slider" type="range" min="${s.dpi_min}" max="${s.dpi_max}" step="${s.dpi_step}" value="${active.y}"/>
                </div>`
              : ""
          }

          <div class="cat-heading" style="margin-top:16px;">${t.dpi.presets}</div>
          <div class="preset-row">
            ${[400, 800, 1600, 3200, 6400]
              .map((v) => `<button class="choice-btn ${active.x === v ? "is-active" : ""}" data-preset="${v}">${v}</button>`)
              .join("")}
          </div>
        </section>
      </div>
    `;

    stage.querySelectorAll("[data-dpi-row]").forEach((row) => {
      row.onclick = (ev) => {
        if (ev.target.tagName === "INPUT") return;
        store.xySplit = false;
        mutate("set_current_dpi", { stage: Number(row.dataset.dpiRow) });
      };
    });

    stage.querySelectorAll("[data-dpi-color]").forEach((inp) => {
      inp.onchange = () => {
        mutate("set_dpi_color", { stage: Number(inp.dataset.dpiColor), color: inp.value });
      };
    });

    document.getElementById("dpi-add").onclick = () => {
      const defaults = [400, 800, 1600, 3200, 6400, 12800];
      const colors = ["#ff0000", "#0000ff", "#00ff00", "#ffff00", "#00ffff", "#7d00ff"];
      const idx = s.dpi_stages.length;
      const next = [...s.dpi_stages, { x: defaults[idx] || 1600, y: defaults[idx] || 1600, color: colors[idx] || "#ff0000" }];
      mutate("set_dpi_stages", { stages: next, active_dpi: s.active_dpi });
    };

    document.getElementById("dpi-rem").onclick = () => {
      const next = s.dpi_stages.slice(0, -1);
      mutate("set_dpi_stages", { stages: next, active_dpi: Math.min(s.active_dpi, next.length - 1) });
    };

    document.getElementById("xy-toggle").onchange = (ev) => {
      store.xySplit = ev.target.checked;
      if (!store.xySplit && active.x !== active.y) {
        mutate("set_dpi_stage", { stage: s.active_dpi, x: active.x, y: active.x });
      } else {
        renderDpiPage();
      }
    };

    const xSlider = document.getElementById("dpi-x-slider");
    const xNum = document.getElementById("dpi-x-num");
    const commitDpi = (x, y) => mutate("set_dpi_stage", { stage: s.active_dpi, x, y });

    xSlider.oninput = () => { xNum.value = xSlider.value; };
    xSlider.onchange = () => {
      const x = Number(xSlider.value);
      const y = isSplit ? Number(document.getElementById("dpi-y-num")?.value || x) : x;
      commitDpi(x, y);
    };
    xNum.onchange = () => {
      const x = Number(xNum.value);
      const y = isSplit ? Number(document.getElementById("dpi-y-num")?.value || x) : x;
      commitDpi(x, y);
    };

    if (isSplit) {
      const ySlider = document.getElementById("dpi-y-slider");
      const yNum = document.getElementById("dpi-y-num");
      ySlider.oninput = () => { yNum.value = ySlider.value; };
      ySlider.onchange = () => commitDpi(Number(xNum.value), Number(ySlider.value));
      yNum.onchange = () => commitDpi(Number(xNum.value), Number(yNum.value));
    }

    stage.querySelectorAll("[data-preset]").forEach((btn) => {
      btn.onclick = () => {
        const v = Number(btn.dataset.preset);
        commitDpi(v, isSplit ? active.y : v);
      };
    });
  }

  function renderPerformancePage() {
    const t = tr();
    const s = store.state;
    const stage = document.getElementById("main-stage");
    const rates = s.polling_options.length ? s.polling_options : [125, 250, 500, 1000, 2000, 4000, 8000];

    stage.innerHTML = `
      <section class="dpi-hero">
        ${window.VgnMouseSvg.renderTop({ ledColor: activeLedColor(), compact: false })}
      </section>

      <div class="perf-grid">
        <section class="card">
          <div class="card-title">${t.perf.pollingTitle}</div>
          <div class="card-sub">${t.perf.pollingDesc}</div>
          <div class="polling-bars">
            ${rates
              .map(
                (hz) => `
              <button class="poll-bar ${s.polling_hz === hz ? "is-active" : ""}"
                      style="height:${POLLING_HEIGHTS[hz] || 55}%"
                      data-hz="${hz}">${hz}Hz</button>`
              )
              .join("")}
          </div>
          <div style="display:flex;justify-content:space-between;font-size:11px;color:var(--text-dim);">
            <span>${t.perf.pollingLow}</span>
            <span>${t.perf.pollingHigh}</span>
          </div>
        </section>

        <section class="card">
          <div class="card-title">${t.perf.samplingTitle}</div>
          <div class="card-sub">${t.perf.samplingDesc}</div>
          <div class="sampling-cards">
            <button class="mode-card ${s.fps_mode === 0 ? "is-active" : ""}" data-fps="0">
              <div class="mode-card-title">${t.perf.basicTitle}</div>
              <div class="mode-card-desc">${t.perf.basicDesc}</div>
            </button>
            <button class="mode-card ${s.fps_mode === 1 ? "is-active" : ""}" data-fps="1">
              <div class="mode-card-title">${t.perf.supremeTitle}</div>
              <div class="mode-card-desc">${t.perf.supremeDesc}</div>
            </button>
          </div>
        </section>
      </div>
    `;

    stage.querySelectorAll("[data-hz]").forEach((b) => {
      b.onclick = () => mutate("set_polling_rate", { hz: Number(b.dataset.hz) });
    });
    stage.querySelectorAll("[data-fps]").forEach((b) => {
      b.onclick = () => mutate("set_fps_mode", { mode: Number(b.dataset.fps) });
    });
  }

  function renderMacrosPage() {
    const t = tr();
    const stage = document.getElementById("main-stage");
    const macros = store.config.macros;
    const cur = macros[store.selectedMacroSlot] || { slot: 0, name: "Macro 1", repeat: 1, events: [] };

    const slotsHtml = macros
      .map(
        (m) => `
      <button class="macro-slot-btn ${m.slot === store.selectedMacroSlot ? "is-active" : ""}" data-mslot="${m.slot}">
        <span>${m.name}</span>
        <span style="opacity:0.7;">${m.events.length}</span>
      </button>`
      )
      .join("");

    const stepsHtml = cur.events.length
      ? cur.events
          .map((ev, idx) => {
            const label =
              ev.device === "mouse"
                ? `Mouse #${ev.code}`
                : hidLabel(ev.code);
            return `
              <div class="macro-step-row">
                <span style="width:22px;color:var(--text-dim);">#${idx + 1}</span>
                <span style="font-weight:700;flex:1;">${label}</span>
                <span style="color:${ev.down ? "#6ee7b7" : "#fbbf24"};width:76px;">${ev.down ? "↓ " + t.macro.down : "↑ " + t.macro.up}</span>
                <input class="num-input" type="number" min="0" max="65535" value="${ev.delay_ms}" data-mdelay="${idx}" style="width:74px;"/>
                <span style="font-size:11px;color:var(--text-dim);">ms</span>
                <button class="seg-btn" data-mdel="${idx}">✕</button>
              </div>`;
          })
          .join("")
      : `<div style="color:var(--text-dim);padding:24px;text-align:center;">${t.macro.emptySteps}</div>`;

    stage.innerHTML = `
      <div class="macro-grid">
        <section class="card" style="padding:12px;">
          <div class="card-title" style="margin-bottom:8px;">${t.macro.listTitle}</div>
          <div class="macro-list">${slotsHtml}</div>
        </section>

        <section class="card" style="display:flex;flex-direction:column;">
          <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;">
            <div class="card-title" style="margin:0;">${t.macro.editorTitle}</div>
            <div style="display:flex;gap:8px;">
              <button id="macro-add-key" class="btn-secondary">${t.macro.addKeyStep}</button>
              <button id="macro-clear" class="btn-secondary">${t.macro.clearEvents}</button>
            </div>
          </div>
          <div style="display:flex;gap:10px;margin-top:10px;">
            <label style="flex:1;font-size:11.5px;color:var(--text-muted);">${t.macro.nameLabel}
              <input id="macro-name" class="text-input full-width" style="margin-top:4px;" value="${escHtml(cur.name)}"/>
            </label>
            <label style="width:110px;font-size:11.5px;color:var(--text-muted);">${t.macro.repeatLabel}
              <input id="macro-repeat" class="num-input full-width" type="number" min="1" max="65535" style="margin-top:4px;" value="${cur.repeat}"/>
            </label>
          </div>
          <div class="macro-steps">${stepsHtml}</div>
        </section>

        <section class="card" style="display:flex;flex-direction:column;justify-content:space-between;">
          <div>
            <div class="card-title">${t.macro.recorderTitle}</div>
            <div id="rec-box" class="rec-box ${store.isRecording ? "is-recording" : ""}" tabindex="0">
              <p style="font-size:12px;color:var(--text-muted);line-height:1.45;">
                ${store.isRecording ? t.macro.recordingHint : t.macro.idleHint}
              </p>
              <button id="btn-rec-toggle" class="${store.isRecording ? "btn-danger" : "btn-primary"}" style="margin-top:12px;">
                ${store.isRecording ? t.macro.stopRec : t.macro.startRec}
              </button>
            </div>
          </div>
          <div style="display:flex;flex-direction:column;gap:8px;">
            <button id="macro-save" class="btn-primary full-width">${t.macro.saveToMouse}</button>
            <button id="macro-read" class="btn-secondary full-width">${t.macro.readFromMouse}</button>
          </div>
        </section>
      </div>
    `;

    stage.querySelectorAll("[data-mslot]").forEach((b) => {
      b.onclick = () => {
        store.isRecording = false;
        store.selectedMacroSlot = Number(b.dataset.mslot);
        renderMacrosPage();
      };
    });

    document.getElementById("macro-name").onchange = (ev) => {
      cur.name = ev.target.value.trim() || `Macro ${cur.slot + 1}`;
      renderMacrosPage();
    };
    document.getElementById("macro-repeat").onchange = (ev) => {
      cur.repeat = Math.max(1, Math.min(65535, Number(ev.target.value) || 1));
    };

    stage.querySelectorAll("[data-mdelay]").forEach((inp) => {
      inp.onchange = () => {
        cur.events[Number(inp.dataset.mdelay)].delay_ms = Math.max(0, Math.min(65535, Number(inp.value) || 0));
      };
    });

    stage.querySelectorAll("[data-mdel]").forEach((btn) => {
      btn.onclick = () => {
        cur.events.splice(Number(btn.dataset.mdel), 1);
        renderMacrosPage();
      };
    });

    document.getElementById("macro-add-key").onclick = () => {
      if (cur.events.length + 2 > 63) return;
      cur.events.push({ device: "keyboard", code: 0x04, down: true, delay_ms: 20 });
      cur.events.push({ device: "keyboard", code: 0x04, down: false, delay_ms: 20 });
      renderMacrosPage();
    };

    document.getElementById("macro-clear").onclick = () => {
      cur.events = [];
      renderMacrosPage();
    };

    const recBox = document.getElementById("rec-box");
    const pushRecorded = (device, code, down) => {
      if (!store.isRecording || cur.events.length >= 63) return;
      const now = performance.now();
      const delay = store.lastRecTime ? Math.min(65535, Math.max(1, Math.round(now - store.lastRecTime))) : 10;
      store.lastRecTime = now;
      cur.events.push({ device, code, down, delay_ms: delay });
      renderMacrosPage();
      document.getElementById("rec-box")?.focus();
    };

    document.getElementById("btn-rec-toggle").onclick = (ev) => {
      ev.stopPropagation();
      store.isRecording = !store.isRecording;
      store.lastRecTime = 0;
      renderMacrosPage();
      if (store.isRecording) document.getElementById("rec-box")?.focus();
    };

    if (store.isRecording) {
      recBox.focus();
      recBox.onkeydown = (ev) => {
        ev.preventDefault();
        if (ev.repeat) return;
        const hid = CODE_TO_HID[ev.code];
        if (hid) pushRecorded("keyboard", hid, true);
      };
      recBox.onkeyup = (ev) => {
        ev.preventDefault();
        const hid = CODE_TO_HID[ev.code];
        if (hid) pushRecorded("keyboard", hid, false);
      };
      recBox.onmousedown = (ev) => {
        if (ev.target.tagName === "BUTTON") return;
        const btnMap = { 0: 1, 2: 2, 1: 3, 4: 4, 3: 5 };
        const code = btnMap[ev.button];
        if (code) pushRecorded("mouse", code, true);
      };
      recBox.onmouseup = (ev) => {
        if (ev.target.tagName === "BUTTON") return;
        const btnMap = { 0: 1, 2: 2, 1: 3, 4: 4, 3: 5 };
        const code = btnMap[ev.button];
        if (code) pushRecorded("mouse", code, false);
      };
    }

    document.getElementById("macro-save").onclick = async () => {
      store.isRecording = false;
      try {
        const res = await rpc("save_macro", cur);
        if (res?.macros) store.config.macros = res.macros;
        showToast(tr().saved);
        renderMacrosPage();
      } catch (err) {
        showToast(tr().errorPrefix + err.message, true);
      }
    };

    document.getElementById("macro-read").onclick = async () => {
      try {
        const res = await rpc("read_macro", { slot: cur.slot });
        if (res?.macro) {
          store.config.macros[cur.slot] = res.macro;
          renderMacrosPage();
        }
      } catch (err) {
        showToast(tr().errorPrefix + err.message, true);
      }
    };
  }

  function renderRotationPage() {
    const t = tr();
    const s = store.state;
    const stage = document.getElementById("main-stage");
    let angle = s.sensor_rotation;

    stage.innerHTML = `
      <section class="dpi-hero">
        ${window.VgnMouseSvg.renderTop({ ledColor: activeLedColor(), compact: false })}
      </section>

      <section class="card rotation-card">
        <div class="rotation-header">
          <span class="tab-btn is-active rotation-pill">${t.nav.rotation}</span>
          <div class="rotation-sub">${t.rotation.desc}</div>
        </div>

        <div class="rotation-layout">
          <div class="rotation-left">
            <div class="dial-controls">
              <div class="step-col">
                <button class="rot-step-btn" data-delta="-1">-1°</button>
                <button class="rot-step-btn" data-delta="-5">-5°</button>
                <button class="rot-step-btn" data-delta="-10">-10°</button>
              </div>

              <div class="dial-stage">
                <div class="dial-interactive" id="rot-dial">
                  ${window.VgnMouseSvg.renderRotationDial({ angle })}
                </div>
                <button id="rot-reset" class="rot-reset-btn">${t.rotation.resetZero}</button>
              </div>

              <div class="step-col">
                <button class="rot-step-btn" data-delta="1">+1°</button>
                <button class="rot-step-btn" data-delta="5">+5°</button>
                <button class="rot-step-btn" data-delta="10">+10°</button>
              </div>
            </div>
          </div>

          <div class="rotation-divider" aria-hidden="true"></div>

          <div class="rotation-right" id="wire-wrap">
            ${window.VgnMouseSvg.renderWireframe({ angle })}
          </div>
        </div>
      </section>
    `;

    const updatePreview = (deg, animate = false) => {
      angle = Math.max(-90, Math.min(90, Math.round(deg)));
      const needleGroup = document.getElementById("rot-needle-group");
      const valEl = document.getElementById("rot-val");
      const arcEl = document.getElementById("rot-active-arc");
      const rimEl = document.getElementById("rot-active-rim");
      const wireGroup = document.getElementById("wire-mouse-group");

      if (needleGroup) {
        needleGroup.classList.toggle("is-smooth", animate);
        needleGroup.setAttribute("transform", `rotate(${angle * 1.5} 148 144)`);
      }
      if (valEl) valEl.textContent = `${angle}°`;
      if (arcEl) arcEl.setAttribute("d", window.VgnMouseSvg.rotationArcPath(148, 144, 88, angle));
      if (rimEl) rimEl.setAttribute("d", window.VgnMouseSvg.rotationArcPath(148, 144, 104, angle));
      if (wireGroup) {
        wireGroup.classList.toggle("is-smooth", animate);
        wireGroup.setAttribute("transform", `rotate(${angle} 105 125)`);
      }
    };

    const commitRotation = (targetDeg) => {
      if (rotCommitTimer) {
        clearTimeout(rotCommitTimer);
        rotCommitTimer = null;
      }
      if (targetDeg !== store.state?.sensor_rotation) {
        mutate("set_sensor_rotation", { degrees: targetDeg });
      }
    };

    stage.querySelectorAll("[data-delta]").forEach((btn) => {
      btn.onclick = () => {
        updatePreview(angle + Number(btn.dataset.delta), true);
        if (rotCommitTimer) clearTimeout(rotCommitTimer);
        rotCommitTimer = setTimeout(() => commitRotation(angle), 220);
      };
    });

    document.getElementById("rot-reset").onclick = () => {
      updatePreview(0, true);
      commitRotation(0);
    };

    const dial = document.getElementById("rot-dial");
    let dragging = false;
    const calcPointerAngle = (ev) => {
      const svg = dial.querySelector(".rot-dial-svg") || dial;
      const rect = svg.getBoundingClientRect();
      const cx = rect.left + rect.width * (148 / 296);
      const cy = rect.top + rect.height * (144 / 254);
      const rawDeg = (Math.atan2(ev.clientX - cx, -(ev.clientY - cy)) * 180) / Math.PI;
      if (Math.abs(rawDeg) > 135) {
        return angle >= 0 ? 90 : -90;
      }
      return Math.max(-90, Math.min(90, Math.round(rawDeg / 1.5)));
    };
    dial.onpointerdown = (ev) => {
      if (rotCommitTimer) {
        clearTimeout(rotCommitTimer);
        rotCommitTimer = null;
      }
      dragging = true;
      dial.setPointerCapture(ev.pointerId);
      updatePreview(calcPointerAngle(ev), false);
    };
    dial.onpointermove = (ev) => {
      if (!dragging) return;
      updatePreview(calcPointerAngle(ev), false);
    };
    dial.onpointerup = () => {
      if (!dragging) return;
      dragging = false;
      commitRotation(angle);
    };
    dial.onpointercancel = () => {
      if (!dragging) return;
      dragging = false;
      updatePreview(store.state.sensor_rotation, true);
    };
  }

  function renderParamsPage() {
    const t = tr();
    const s = store.state;
    const stage = document.getElementById("main-stage");

    const toggleCard = (id, title, desc, checked) => `
      <section class="card">
        <div class="param-header">
          <div>
            <div class="card-title">${title}</div>
            <div class="card-sub" style="margin:0;">${desc}</div>
          </div>
          <label class="switch">
            <input type="checkbox" id="${id}" ${checked ? "checked" : ""}/>
            <span class="switch-track"></span>
          </label>
        </div>
      </section>
    `;

    stage.innerHTML = `
      <div class="params-grid">
        <section class="card">
          <div class="card-title">${t.params.lodTitle}</div>
          <div class="card-sub">${t.params.lodDesc}</div>
          <div class="pill-choices">
            ${s.lod_options
              .map((o) => `<button class="choice-btn ${s.lod_code === o.code ? "is-active" : ""}" data-lod="${o.code}">${o.label}</button>`)
              .join("")}
          </div>
        </section>

        <section class="card">
          <div class="card-title">${t.params.latencyTitle}</div>
          <div class="card-sub">${t.params.latencyDesc}</div>
          <div class="pill-choices">
            <button class="choice-btn ${s.latency_mode === 0 ? "is-active" : ""}" data-lat="0">${t.params.stableMode}</button>
            <button class="choice-btn ${s.latency_mode === 1 ? "is-active" : ""}" data-lat="1">${t.params.extremeMode}</button>
          </div>
        </section>

        ${toggleCard("sw-motion", t.params.motionSyncTitle, t.params.motionSyncDesc, s.motion_sync)}

        <section class="card">
          <div class="card-title">${t.params.debounceTitle}</div>
          <div class="card-sub">${t.params.debounceDesc}</div>
          <div class="pill-choices">
            ${DEBOUNCE_OPTIONS.map((ms) => `<button class="choice-btn ${s.debounce_ms === ms ? "is-active" : ""}" data-deb="${ms}">${ms}ms</button>`).join("")}
          </div>
        </section>

        ${toggleCard("sw-angle", t.params.angleSnapTitle, t.params.angleSnapDesc, s.angle_snap)}

        <section class="card">
          <div class="card-title">${t.params.sleepTitle}</div>
          <div class="card-sub">${t.params.sleepDesc}</div>
          <div class="pill-choices">
            ${SLEEP_OPTIONS.map((o) => `<button class="choice-btn ${s.sleep_seconds === o.sec ? "is-active" : ""}" data-sleep="${o.sec}">${o.label}</button>`).join("")}
          </div>
        </section>

        ${toggleCard("sw-ripple", t.params.rippleTitle, t.params.rippleDesc, s.ripple_control)}
      </div>
    `;

    stage.querySelectorAll("[data-lod]").forEach((b) => {
      b.onclick = () => mutate("set_lod", { code: Number(b.dataset.lod) });
    });
    stage.querySelectorAll("[data-lat]").forEach((b) => {
      b.onclick = () => mutate("set_latency_mode", { mode: Number(b.dataset.lat) });
    });
    stage.querySelectorAll("[data-deb]").forEach((b) => {
      b.onclick = () => mutate("set_debounce", { ms: Number(b.dataset.deb) });
    });
    stage.querySelectorAll("[data-sleep]").forEach((b) => {
      b.onclick = () => mutate("set_sleep_time", { seconds: Number(b.dataset.sleep) });
    });
    document.getElementById("sw-motion").onchange = (ev) => mutate("set_motion_sync", { enabled: ev.target.checked });
    document.getElementById("sw-angle").onchange = (ev) => mutate("set_angle_snap", { enabled: ev.target.checked });
    document.getElementById("sw-ripple").onchange = (ev) => mutate("set_ripple_control", { enabled: ev.target.checked });
  }

  function renderSystemPage() {
    const t = tr();
    const s = store.state;
    const stage = document.getElementById("main-stage");
    const waybarSnippet = `"custom/vgn-mouse": {\n  "exec": "vgn-hub battery --waybar",\n  "return-type": "json",\n  "interval": 30\n}`;
    const modelsHtml = store.catalog.supported_models
      .map(
        (m) => `
      <div class="tel-row" style="padding:6px 0;border-bottom:1px solid var(--border-subtle);">
        <span style="font-weight:600;">${m.name}</span>
        <span style="color:var(--text-muted);font-size:11.5px;">${m.sensor} · ${m.dpi_max} DPI · ${m.wired_vid_pid} / ${m.wireless_vid_pid}</span>
      </div>`
      )
      .join("");

    stage.innerHTML = `
      <div class="params-grid">
        <section class="card">
          <div class="card-title">${t.system.backupTitle}</div>
          <div class="card-sub">${t.system.backupDesc}</div>
          <div style="display:flex;gap:10px;flex-wrap:wrap;">
            <button id="sys-export" class="btn-primary">${t.system.exportBtn}</button>
            <button id="sys-import" class="btn-secondary">${t.system.importBtn}</button>
          </div>
        </section>

        <section class="card">
          <div class="card-title">${t.system.prefsTitle}</div>
          <div class="card-sub">v${store.catalog.app_version || "0.1.0"}</div>
          <div class="pill-choices">
            <button class="choice-btn ${store.config.theme === "glass" ? "is-active" : ""}" data-set-theme="glass">${t.system.glassLabel}</button>
            <button class="choice-btn ${store.config.theme === "solid" ? "is-active" : ""}" data-set-theme="solid">${t.system.solidLabel}</button>
            <button class="choice-btn ${store.config.lang === "vi" ? "is-active" : ""}" data-set-lang="vi">Tiếng Việt</button>
            <button class="choice-btn ${store.config.lang === "en" ? "is-active" : ""}" data-set-lang="en">English</button>
          </div>
        </section>
      </div>

      <section class="card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
          <div class="card-title" style="margin:0;">${t.system.waybarTitle}</div>
          <button id="sys-copy-waybar" class="btn-secondary">${t.system.copyWaybar}</button>
        </div>
        <div class="card-sub">${t.system.waybarDesc}</div>
        <pre class="code-block">${waybarSnippet}</pre>
      </section>

      <div class="params-grid">
        <section class="card">
          <div class="card-title">${t.system.deviceTitle}</div>
          <div class="card-sub">${s.device_name} (${s.vid_pid}) · ${s.hidraw_path} · fw v${s.firmware}</div>
          <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;">
            <span class="pill ${store.catalog.udev_rule_installed ? "pill-ok" : "pill-err"}">
              ${store.catalog.udev_rule_installed ? t.system.udevOk : t.system.udevMissing}
            </span>
            <button id="sys-factory" class="btn-danger">${t.restoreDefault}</button>
          </div>
        </section>

        <section class="card">
          <div class="card-title">${t.system.modelsTitle}</div>
          <div style="margin-top:8px;">${modelsHtml}</div>
        </section>
      </div>
    `;

    document.getElementById("sys-export").onclick = async () => {
      try {
        const res = await rpc("export_backup_dialog");
        if (res && !res.cancelled) showToast(res.path);
      } catch (err) {
        showToast(tr().errorPrefix + err.message, true);
      }
    };

    document.getElementById("sys-import").onclick = async () => {
      try {
        const res = await rpc("import_backup_dialog");
        if (res && res.state) {
          store.state = res.state;
          renderAll();
          showToast(tr().saved);
        }
      } catch (err) {
        showToast(tr().errorPrefix + err.message, true);
      }
    };

    document.getElementById("sys-copy-waybar").onclick = async () => {
      try {
        await navigator.clipboard.writeText(waybarSnippet);
        showToast(t.system.copied);
      } catch {
        showToast("Clipboard unavailable", true);
      }
    };

    stage.querySelectorAll("[data-set-theme]").forEach((b) => {
      b.onclick = () => setUiPrefs({ theme: b.dataset.setTheme });
    });
    stage.querySelectorAll("[data-set-lang]").forEach((b) => {
      b.onclick = () => setUiPrefs({ lang: b.dataset.setLang });
    });

    document.getElementById("sys-factory").onclick = () => {
      openConfirm(t.restoreConfirmTitle, t.restoreConfirmBody, () => mutate("restore_factory"));
    };
  }

  function renderStage() {
    if (!store.connected || !store.state) {
      renderDisconnected();
      return;
    }
    const views = {
      keys: renderKeysPage,
      dpi: renderDpiPage,
      performance: renderPerformancePage,
      macros: renderMacrosPage,
      rotation: renderRotationPage,
      params: renderParamsPage,
      system: renderSystemPage,
    };
    (views[store.page] || renderKeysPage)();
  }

  function renderAll() {
    renderChrome();
    renderStage();
  }

  async function setUiPrefs(prefs) {
    Object.assign(store.config, prefs);
    renderAll();
    try {
      await rpc("set_ui_prefs", prefs);
    } catch (_) {}
  }

  function applyBundle(bundle) {
    store.connected = Boolean(bundle.connected);
    store.error = bundle.error || "";
    store.state = bundle.state || null;
    if (bundle.config) store.config = bundle.config;
    if (bundle.catalog) store.catalog = bundle.catalog;
    renderAll();
  }

  async function boot() {
    try {
      const bundle = await rpc("init");
      applyBundle(bundle);
    } catch (err) {
      store.connected = false;
      store.error = err.message;
      renderAll();
    }
  }

  document.getElementById("btn-refresh").onclick = async () => {
    try {
      const bundle = await rpc("refresh");
      applyBundle(bundle);
    } catch (err) {
      showToast(tr().errorPrefix + err.message, true);
    }
  };

  document.getElementById("btn-theme").onclick = () => {
    setUiPrefs({ theme: store.config.theme === "glass" ? "solid" : "glass" });
  };

  document.getElementById("btn-lang").onclick = () => {
    setUiPrefs({ lang: store.config.lang === "vi" ? "en" : "vi" });
  };

  document.getElementById("btn-demo-toggle").onclick = async () => {
    const action = store.connected && store.state?.is_demo ? "connect_real" : "enter_demo";
    try {
      const bundle = await rpc(action);
      applyBundle(bundle);
    } catch (err) {
      showToast(tr().errorPrefix + err.message, true);
    }
  };

  window.addEventListener("DOMContentLoaded", boot);
})();
