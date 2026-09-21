// =============================================================================
// CREVANTA STUDIO — CLIENT CONTROLLER
// Luxury Editorial Automation Portal for Real-Time AI Creator Partnerships
// 100% Native Local AI Architecture Powered by Ollama & Gmail SMTP/IMAP
// =============================================================================

let appState = {
  creators: [],
  selectedCreatorId: null,
  creatorMode: "roster", // 'roster' or 'custom'
  aiProvider: "ollama",
  ollamaRunning: false,
  ollamaModels: [],
  ollamaBaseUrl: "http://127.0.0.1:11434",
  ollamaModel: "qwen2.5:7b",
  generatedBrands: [],
  selectedBrandIds: new Set(),
  savedCommands: [],
  history: [],
  selectedLocation: "All India",
  isAutoPilot: false,
  activeBulkJobId: null,
  bulkPollInterval: null,
  pendingDispatchMode: "send",
  talks: [],
  activeTalkId: null,
  chatMessages: [
    {
      role: "assistant",
      content: "Welcome to Crevanta Studio. Select a creator or define a custom talent profile, configure your unique video idea and 15-day campaign milestones, and command me to discover authentic brand partners in real time."
    }
  ]
};

// --- INITIALIZATION ---
document.addEventListener("DOMContentLoaded", async () => {
  if (window.lucide) lucide.createIcons();
  await loadStatus();
  await loadCreators();
  await loadCommands();
  await loadHistory();
  await loadTalks();
  await refreshBrandMemoryBadge();

  // Attach listener to brand count select
  const countSelect = document.getElementById("brandCountSelect");
  if (countSelect) {
    countSelect.addEventListener("change", updateGenerateButtonText);
  }
});

// --- ANTI-REPETITION BRAND MEMORY ---
async function refreshBrandMemoryBadge() {
  const badge = document.getElementById("antiRepetitionMemoryBadge");
  if (!badge) return;
  try {
    const res = await fetch("/api/memory/pitched-brands");
    if (res.ok) {
      const data = await res.json();
      const count = data.count || 0;
      badge.innerText = `Anti-Repetition Memory: ${count} Brands Remembered`;
    } else {
      badge.innerText = "Anti-Repetition Memory: Active";
    }
  } catch (e) {
    badge.innerText = "Anti-Repetition Memory: Active";
  }
  if (window.lucide) lucide.createIcons();
}

async function clearBrandMemory() {
  if (!confirm("Are you sure you want to reset the brand discovery memory? This will clear the exclusion list and allow previously pitched brands to be discovered again.")) {
    return;
  }
  try {
    const res = await fetch("/api/memory/pitched-brands", { method: "DELETE" });
    if (res.ok) {
      showToast("Anti-repetition memory reset. Brand exclusion list cleared.");
      await refreshBrandMemoryBadge();
    } else {
      showToast("Failed to reset brand memory.", false);
    }
  } catch (err) {
    showToast("Error resetting brand memory: " + err.message, false);
  }
}

// --- TOAST NOTIFICATIONS ---
function showToast(msg, isSuccess = true) {
  const toast = document.getElementById("toast");
  const toastMsg = document.getElementById("toastMsg");
  const toastIcon = document.getElementById("toastIcon");

  if (!toast || !toastMsg || !toastIcon) return;
  toastMsg.innerText = msg;
  toastIcon.setAttribute("data-lucide", isSuccess ? "check-circle" : "alert-circle");
  toastIcon.className = `w-4 h-4 ${isSuccess ? "text-[#A68A5B]" : "text-rose-500"}`;
  if (window.lucide) lucide.createIcons();

  toast.classList.remove("translate-y-20", "opacity-0");
  toast.classList.add("translate-y-0", "opacity-100");

  setTimeout(() => {
    toast.classList.add("translate-y-20", "opacity-0");
    toast.classList.remove("translate-y-0", "opacity-100");
  }, 4000);
}

// --- TAB SWITCHING ---
function switchTab(tabName) {
  const tabs = ["studio", "creators", "chat", "playbook", "history"];
  tabs.forEach(t => {
    const view = document.getElementById(`view-${t}`);
    const btn = document.getElementById(`tab-${t}`);
    if (view && btn) {
      if (t === tabName) {
        view.classList.remove("hidden");
        btn.classList.add("active");
      } else {
        view.classList.add("hidden");
        btn.classList.remove("active");
      }
    }
  });
  if (window.lucide) lucide.createIcons();
}

// --- CREATOR MODE TOGGLE (ROSTER VS CUSTOM DYNAMIC) ---
function setCreatorMode(mode) {
  appState.creatorMode = mode;
  const rosterBox = document.getElementById("rosterSelectionBox");
  const customBox = document.getElementById("customCreatorBox");
  const toggleRoster = document.getElementById("toggleRosterBtn");
  const toggleCustom = document.getElementById("toggleCustomBtn");

  if (mode === "custom") {
    if (rosterBox) rosterBox.classList.add("hidden");
    if (customBox) customBox.classList.remove("hidden");
    if (toggleCustom) toggleCustom.className = "px-3 py-1 text-xs font-semibold rounded bg-[#171717] text-white transition";
    if (toggleRoster) toggleRoster.className = "px-3 py-1 text-xs font-semibold rounded text-[#696963] hover:text-[#171717] transition";
  } else {
    if (rosterBox) rosterBox.classList.remove("hidden");
    if (customBox) customBox.classList.add("hidden");
    if (toggleRoster) toggleRoster.className = "px-3 py-1 text-xs font-semibold rounded bg-[#171717] text-white transition";
    if (toggleCustom) toggleCustom.className = "px-3 py-1 text-xs font-semibold rounded text-[#696963] hover:text-[#171717] transition";
  }
}

// --- SYSTEM STATUS & LOCAL OLLAMA AI ---
async function loadStatus() {
  try {
    const res = await fetch("/api/status");
    const status = await res.json();

    appState.aiProvider = "ollama";
    appState.ollamaBaseUrl = status.ollama_base_url || "http://127.0.0.1:11434";
    appState.ollamaModel = status.ollama_model || "llama3.2:1b";

    // Update settings form fields
    const inputOllamaUrl = document.getElementById("inputOllamaBaseUrl");
    const inputOllamaModel = document.getElementById("inputOllamaModel");
    const inputGmail = document.getElementById("inputGmailUser");
    const inputAgency = document.getElementById("inputAgencyName");
    const inputSender = document.getElementById("inputSenderName");

    if (inputOllamaUrl) inputOllamaUrl.value = appState.ollamaBaseUrl;
    if (inputOllamaModel) inputOllamaModel.value = appState.ollamaModel;
    if (inputAgency && status.agency_name) inputAgency.value = status.agency_name;
    if (inputSender && status.sender_name) inputSender.value = status.sender_name;
    if (inputGmail && status.gmail_user) inputGmail.value = status.gmail_user;

    // Check live Ollama daemon
    await checkOllamaStatus();

    // Update dynamic badges
    updateAiBadge();

    // Gmail status badge
    const gmailBadge = document.getElementById("gmailStatusBadge");
    const gmailText = document.getElementById("gmailStatusText");
    const gmailDot = document.getElementById("gmailStatusDot");
    if (status.gmail_configured && status.gmail_user) {
      if (gmailBadge) gmailBadge.className = "editorial-badge badge-active cursor-pointer transition hover:opacity-90";
      if (gmailText) gmailText.innerText = `Gmail: ${status.gmail_user}`;
      if (gmailDot) gmailDot.className = "w-2 h-2 rounded-full bg-emerald-500";
    } else {
      if (gmailBadge) gmailBadge.className = "editorial-badge badge-warning cursor-pointer transition hover:opacity-90";
      if (gmailText) gmailText.innerText = "Gmail: Connect Account";
      if (gmailDot) gmailDot.className = "w-2 h-2 rounded-full bg-amber-500";
    }

    if (window.lucide) lucide.createIcons();
  } catch (err) {
    console.error("Failed to load status:", err);
  }
}

function updateAiBadge() {
  const badge = document.getElementById("aiStatusBadge");
  const text = document.getElementById("aiStatusText");
  const dot = document.getElementById("aiStatusDot");
  const hint = document.getElementById("aiActionHint");
  if (!badge || !text) return;

  if (appState.ollamaRunning) {
    badge.className = "editorial-badge badge-active cursor-pointer transition hover:opacity-90 flex items-center gap-2";
    text.innerText = `Ollama: ON (${appState.ollamaModel || '1b'})`;
    if (dot) dot.className = "w-2 h-2 rounded-full bg-emerald-500 shadow-sm";
    if (hint) {
      hint.innerText = "Click to Turn OFF";
      hint.className = "text-[10px] text-[#A68A5B] font-normal border-l border-[#D9D6CE] pl-2 hidden sm:inline";
    }
  } else {
    badge.className = "editorial-badge badge-warning cursor-pointer transition hover:opacity-90 flex items-center gap-2";
    text.innerText = "Ollama: OFF";
    if (dot) dot.className = "w-2 h-2 rounded-full bg-amber-500 animate-pulse";
    if (hint) {
      hint.innerText = "Click to Turn ON";
      hint.className = "text-[10px] text-amber-700 font-bold border-l border-amber-200 pl-2 hidden sm:inline";
    }
  }
  updateGenerateButtonText();
}

async function toggleOllamaOneClick() {
  const badge = document.getElementById("aiStatusBadge");
  const text = document.getElementById("aiStatusText");
  const dot = document.getElementById("aiStatusDot");
  const hint = document.getElementById("aiActionHint");

  if (badge) badge.disabled = true;
  if (text) text.innerText = appState.ollamaRunning ? "Stopping..." : "Starting...";
  if (dot) dot.className = "w-2 h-2 rounded-full bg-amber-500 animate-spin";
  if (hint) hint.innerText = "Processing...";

  try {
    const res = await fetch("/api/ollama/toggle", { method: "POST" });
    const data = await res.json();
    if (data.success) {
      appState.ollamaRunning = !!data.running;
      if (data.models && data.models.length) {
        appState.ollamaModels = data.models;
      }
      if (data.running) {
        showToast("🟢 Ollama turned ON & ready! Models loaded.", true);
      } else {
        showToast("⚡ Ollama turned OFF. RAM & CPU freed.", true);
      }
    } else {
      showToast(data.message || "Failed to toggle Ollama", false);
    }
  } catch (err) {
    showToast("Error toggling Ollama: " + err.message, false);
  } finally {
    await checkOllamaStatus();
    updateAiBadge();
    renderOllamaControlStatus();
    if (badge) badge.disabled = false;
    if (window.lucide) lucide.createIcons();
  }
}

function updateGenerateButtonText() {
  const btnText = document.getElementById("generateBtnText");
  const countSelect = document.getElementById("brandCountSelect");
  const count = countSelect ? countSelect.value : "50";
  if (!btnText) return;
  btnText.innerText = `Discover & Pitch ${count} Brands with Ollama (Local)`;
}

function handleAiBadgeClick() {
  openOllamaControlModal();
}

async function checkOllamaStatus() {
  try {
    const res = await fetch("/api/ollama/status");
    const data = await res.json();
    appState.ollamaRunning = !!data.running;
    appState.ollamaModels = data.models || [];
    return data;
  } catch (err) {
    appState.ollamaRunning = false;
    appState.ollamaModels = [];
    return { running: false, error: err.message };
  }
}

function openOllamaControlModal() {
  const modal = document.getElementById("ollamaControlModal") || document.getElementById("ollamaGuideModal");
  if (modal) modal.classList.remove("hidden");
  refreshOllamaControlModal();
  if (window.lucide) lucide.createIcons();
}

function closeOllamaControlModal() {
  const modal = document.getElementById("ollamaControlModal") || document.getElementById("ollamaGuideModal");
  if (modal) modal.classList.add("hidden");
}

// Backwards compatibility aliases
function openOllamaGuideModal() { openOllamaControlModal(); }
function closeOllamaGuideModal() { closeOllamaControlModal(); }

async function refreshOllamaControlModal(userTriggered = false) {
  const btn = document.getElementById("btnRefreshOllamaModal");
  if (userTriggered && btn) {
    btn.disabled = true;
    btn.innerHTML = `<i data-lucide="loader" class="w-3.5 h-3.5 animate-spin"></i><span>Checking...</span>`;
    if (window.lucide) lucide.createIcons();
  }

  await checkOllamaStatus();
  updateAiBadge();
  renderOllamaControlStatus();

  if (userTriggered && btn) {
    btn.disabled = false;
    btn.innerHTML = `<i data-lucide="refresh-cw" class="w-3.5 h-3.5"></i><span>Refresh Status</span>`;
    if (window.lucide) lucide.createIcons();
    showToast(appState.ollamaRunning ? "Ollama daemon is active!" : "Ollama daemon is currently offline.", appState.ollamaRunning);
  }
}

function renderOllamaControlStatus() {
  const box = document.getElementById("ollamaStatusBox");
  const dot = document.getElementById("ollamaModalDot");
  const title = document.getElementById("ollamaModalStatusTitle");
  const desc = document.getElementById("ollamaModalStatusDesc");
  const actionArea = document.getElementById("ollamaPowerActionArea");
  const badge = document.getElementById("ollamaActiveModelBadge");
  const timestamp = document.getElementById("ollamaStatusTimestamp");
  const cardFlagship = document.getElementById("modelCardFlagship");
  const cardTurbo = document.getElementById("modelCardTurbo");
  const cardStandard = document.getElementById("modelCardStandard");

  if (timestamp) {
    timestamp.innerText = `Checked at ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`;
  }

  if (badge) {
    badge.innerText = `Active: ${appState.ollamaModel}`;
  }

  const isFlagship = (appState.ollamaModel || "").includes("qwen");
  const isTurbo = (appState.ollamaModel || "").includes("1b");
  const isStandard = !isFlagship && !isTurbo;

  if (cardFlagship) {
    cardFlagship.className = isFlagship
      ? "p-2.5 border rounded cursor-pointer transition border-purple-600 bg-purple-50/70 ring-2 ring-purple-600 shadow-sm"
      : "p-2.5 border border-[#D9D6CE] rounded cursor-pointer transition hover:border-[#171717] bg-[#F7F5F0]";
  }
  if (cardTurbo) {
    cardTurbo.className = isTurbo
      ? "p-2.5 border rounded cursor-pointer transition border-[#171717] bg-[#EFECE6] ring-1 ring-[#171717] shadow-sm"
      : "p-2.5 border border-[#D9D6CE] rounded cursor-pointer transition hover:border-[#171717] bg-[#F7F5F0]";
  }
  if (cardStandard) {
    cardStandard.className = isStandard
      ? "p-2.5 border rounded cursor-pointer transition border-[#171717] bg-[#EFECE6] ring-1 ring-[#171717] shadow-sm"
      : "p-2.5 border border-[#D9D6CE] rounded cursor-pointer transition hover:border-[#171717] bg-[#F7F5F0]";
  }

  if (appState.ollamaRunning) {
    if (box) box.className = "p-4 rounded border transition bg-emerald-50/80 border-emerald-200 text-emerald-950";
    if (dot) dot.className = "w-2.5 h-2.5 rounded-full bg-emerald-500 shadow-sm animate-pulse";
    if (title) {
      title.innerText = "Service Online & Active";
      title.className = "text-xs font-bold uppercase tracking-wider text-emerald-800";
    }
    if (desc) {
      desc.innerHTML = `Daemon is listening at <code class="font-mono bg-emerald-100/70 px-1 py-0.5 rounded text-[11px]">${appState.ollamaBaseUrl}</code>. Ready for zero-latency local brand pitch generation and real-time talk sessions.`;
    }
    if (actionArea) {
      actionArea.innerHTML = `
        <button onclick="stopOllamaAction()" id="btnPowerToggle" class="w-full py-3 px-4 bg-rose-50 hover:bg-rose-100 border border-rose-300 text-rose-800 rounded font-semibold text-xs flex items-center justify-center gap-2 transition shadow-sm group cursor-pointer">
          <i data-lucide="power" class="w-4 h-4 text-rose-600 group-hover:scale-110 transition-transform"></i>
          <span>Turn OFF Ollama Service (Free RAM & Battery)</span>
        </button>
        <p class="text-[11px] text-[#696963] mt-1 text-center">Stops background daemon and immediately frees ~1.5GB RAM on your Mac.</p>
      `;
    }
  } else {
    if (box) box.className = "p-4 rounded border transition bg-amber-50/80 border-amber-200 text-amber-950";
    if (dot) dot.className = "w-2.5 h-2.5 rounded-full bg-amber-500 shadow-sm";
    if (title) {
      title.innerText = "Service Offline / Idle";
      title.className = "text-xs font-bold uppercase tracking-wider text-amber-800";
    }
    if (desc) {
      desc.innerHTML = `Ollama service is currently shut down. 0% RAM & 0% CPU used. Click <strong>Turn ON</strong> below to start without touching the terminal.`;
    }
    if (actionArea) {
      actionArea.innerHTML = `
        <button onclick="startOllamaAction()" id="btnPowerToggle" class="w-full py-3 px-4 bg-[#171717] hover:bg-[#2d2d2a] border border-[#171717] text-[#F7F5F0] rounded font-semibold text-xs flex items-center justify-center gap-2 transition shadow-sm group cursor-pointer">
          <i data-lucide="play" class="w-4 h-4 text-emerald-400 group-hover:scale-110 transition-transform"></i>
          <span>Turn ON Ollama Service (1-Click Start)</span>
        </button>
        <p class="text-[11px] text-[#696963] mt-1 text-center">Launches local Ollama daemon on port 11434 in 1 click.</p>
      `;
    }
  }

  if (window.lucide) lucide.createIcons();
}

async function startOllamaAction() {
  const btn = document.getElementById("btnPowerToggle");
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<i data-lucide="loader" class="w-4 h-4 animate-spin text-[#A68A5B]"></i><span>Starting Ollama daemon...</span>`;
    if (window.lucide) lucide.createIcons();
  }

  try {
    const res = await fetch("/api/ollama/start", { method: "POST" });
    const data = await res.json();
    if (data.success) {
      showToast("Ollama service started successfully!");
      appState.ollamaRunning = true;
      if (data.models && data.models.length) {
        appState.ollamaModels = data.models;
      }
    } else {
      showToast(data.message || "Failed to start Ollama", false);
    }
  } catch (err) {
    showToast("Error starting Ollama: " + err.message, false);
  } finally {
    await checkOllamaStatus();
    updateAiBadge();
    renderOllamaControlStatus();
    if (window.lucide) lucide.createIcons();
  }
}

async function stopOllamaAction() {
  const btn = document.getElementById("btnPowerToggle");
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<i data-lucide="loader" class="w-4 h-4 animate-spin text-rose-500"></i><span>Stopping Ollama daemon...</span>`;
    if (window.lucide) lucide.createIcons();
  }

  try {
    const res = await fetch("/api/ollama/stop", { method: "POST" });
    const data = await res.json();
    if (data.success) {
      showToast("Ollama stopped. RAM & CPU freed.");
      appState.ollamaRunning = false;
    } else {
      showToast(data.message || "Failed to stop Ollama", false);
    }
  } catch (err) {
    showToast("Error stopping Ollama: " + err.message, false);
  } finally {
    await checkOllamaStatus();
    updateAiBadge();
    renderOllamaControlStatus();
    if (window.lucide) lucide.createIcons();
  }
}

async function switchOllamaModelAction(modelName) {
  try {
    const res = await fetch("/api/ollama/switch-model", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: modelName })
    });
    const data = await res.json();
    if (data.success) {
      appState.ollamaModel = modelName;
      updateAiBadge();
      renderOllamaControlStatus();
      showToast(`Switched active model to ${modelName}`);
    } else {
      showToast("Could not switch model", false);
    }
  } catch (err) {
    showToast("Failed to switch model: " + err.message, false);
  }
}


async function testOllamaLiveConnection() {
  const btnText = document.getElementById("btnTestOllamaText");
  if (btnText) btnText.innerText = "Checking...";
  const status = await checkOllamaStatus();
  updateAiBadge();
  if (status.running) {
    showToast(`Connected to Ollama! Found ${status.models.length} model(s).`);
  } else {
    showToast("Ollama is offline. Run 'ollama serve' in terminal.", false);
  }
  if (btnText) btnText.innerText = "Test Connection";
}

// --- LIVE GMAIL VERIFICATION ---
async function runGmailLiveVerification() {
  const modal = document.getElementById("gmailVerifyModal");
  const content = document.getElementById("gmailVerifyContent");
  if (!modal || !content) return;

  modal.classList.remove("hidden");
  content.innerHTML = `
    <div class="p-4 rounded bg-[#F7F5F0] border border-[#D9D6CE] text-center">
      <i data-lucide="loader-2" class="w-6 h-6 animate-spin mx-auto text-[#A68A5B]"></i>
      <p class="text-xs text-[#696963] mt-2 font-medium">Connecting to smtp.gmail.com:465 & imap.gmail.com:993...</p>
    </div>
  `;
  if (window.lucide) lucide.createIcons();

  try {
    const res = await fetch("/api/gmail/verify");
    const result = await res.json();

    if (result.connected) {
      content.innerHTML = `
        <div class="p-4 rounded bg-[#E8F5E9] border border-[#C8E6C9] space-y-2">
          <div class="flex items-center gap-2 text-[#2E7D32] font-bold text-sm">
            <i data-lucide="check-circle-2" class="w-5 h-5"></i>
            <span>Gmail Authentication Verified</span>
          </div>
          <p class="text-xs text-[#2E7D32] leading-relaxed">
            Successfully connected to Gmail as <strong class="font-mono">${result.user}</strong>. Both SMTP (live delivery) and IMAP (draft saving) are active and ready.
          </p>
        </div>
      `;
      await loadStatus();
    } else {
      content.innerHTML = `
        <div class="p-4 rounded bg-[#FFF8E1] border border-[#FFE082] space-y-2">
          <div class="flex items-center gap-2 text-[#F57F17] font-bold text-sm">
            <i data-lucide="alert-triangle" class="w-5 h-5"></i>
            <span>Connection Incomplete</span>
          </div>
          <p class="text-xs text-[#696963] leading-relaxed">${result.message}</p>
          <div class="pt-2 text-[11px] text-[#696963] border-t border-[#FFE082]/60">
            <strong>Checklist:</strong>
            <ol class="list-decimal list-inside mt-1 space-y-0.5">
              <li>Enable Google 2-Step Verification</li>
              <li>Generate a 16-character App Password at myaccount.google.com/apppasswords</li>
              <li>Enter both in Crevanta Settings</li>
            </ol>
          </div>
        </div>
      `;
    }
  } catch (err) {
    content.innerHTML = `
      <div class="p-4 rounded bg-red-50 border border-red-200 text-red-700 text-xs">
        <strong>Error connecting:</strong> ${err.message}
      </div>
    `;
  }
  if (window.lucide) lucide.createIcons();
}

function closeGmailVerifyModal() {
  const modal = document.getElementById("gmailVerifyModal");
  if (modal) modal.classList.add("hidden");
}

// --- LOAD CREATORS ---
async function loadCreators() {
  try {
    const res = await fetch("/api/creators");
    appState.creators = await res.json();

    const countElem = document.getElementById("creatorCount");
    if (countElem) countElem.innerText = appState.creators.length;

    renderCreatorDropdown();
    renderCreatorsGrid();
    onCreatorChange();
  } catch (err) {
    console.error("Failed to load creators:", err);
  }
}

function renderCreatorDropdown() {
  const select = document.getElementById("studioCreatorSelect");
  const verifierSelect = document.getElementById("verifierCreatorSelect");

  if (select) {
    select.innerHTML = "";
    appState.creators.forEach((c, idx) => {
      const opt = document.createElement("option");
      opt.value = c.id;
      opt.textContent = `${c.name} (${c.handle}) — ${c.niche}`;
      if (idx === 0 && !appState.selectedCreatorId) {
        appState.selectedCreatorId = c.id;
      }
      select.appendChild(opt);
    });

    if (appState.selectedCreatorId) {
      select.value = appState.selectedCreatorId;
    }
  }

  if (verifierSelect) {
    verifierSelect.innerHTML = "";
    appState.creators.forEach((c) => {
      const opt = document.createElement("option");
      opt.value = c.id;
      opt.textContent = `${c.name} (${c.handle}) — ${c.niche}`;
      verifierSelect.appendChild(opt);
    });
  }
}

function onCreatorChange() {
  const select = document.getElementById("studioCreatorSelect");
  const creatorId = select ? select.value : appState.selectedCreatorId;
  appState.selectedCreatorId = creatorId;

  const creator = appState.creators.find(c => c.id === creatorId);
  const card = document.getElementById("creatorPreviewCard");
  const part1Input = document.getElementById("part1Notes");

  if (!creator || !card) return;

  // Auto-fill Part 1 notes if empty or previous placeholder
  if (part1Input && (!part1Input.value || part1Input.value.startsWith("Bio:"))) {
    part1Input.value = `Bio: ${creator.bio}\nNiche: ${creator.niche} | Engagement: ${creator.engagement_rate} | Avg Views: ${creator.avg_views}`;
  }

  card.innerHTML = `
    <div class="flex items-center gap-3.5">
      <div class="w-12 h-12 rounded-full bg-[#141413] text-[#FAF8F5] flex items-center justify-center font-serif text-xl font-bold border-2 border-[#B89248] shadow-sm">
        ${creator.name.charAt(0)}
      </div>
      <div>
        <div class="font-serif text-lg font-bold text-[#141413] flex items-center gap-2">
          <span>${creator.name}</span>
          <span class="text-xs font-sans font-medium text-[#B89248] bg-[#FAF5EB] px-2 py-0.5 rounded border border-[#E8D7B8]">${creator.handle}</span>
        </div>
        <div class="text-xs text-[#66615B] font-semibold mt-0.5">${creator.niche}</div>
      </div>
    </div>

    <div class="flex flex-wrap items-center gap-2.5 text-[#141413] text-xs">
      <div class="studio-metric-pill">
        <i data-lucide="users" class="w-3.5 h-3.5 text-[#B89248]"></i>
        <span><strong>${creator.followers}</strong> Followers</span>
      </div>
      <div class="studio-metric-pill">
        <i data-lucide="trending-up" class="w-3.5 h-3.5 text-[#15803D]"></i>
        <span><strong>${creator.engagement_rate}</strong> ER</span>
      </div>
      <div class="studio-metric-pill">
        <i data-lucide="play-circle" class="w-3.5 h-3.5 text-[#141413]"></i>
        <span><strong>${creator.avg_views}</strong> Avg Views</span>
      </div>
    </div>

    <div class="hidden xl:block text-right text-xs text-[#66615B] max-w-xs truncate">
      <span class="font-bold text-[#141413]">Angle:</span> ${creator.collab_angles || "High Conversion Feature"}
    </div>
  `;
  if (window.lucide) lucide.createIcons();
}

function renderCreatorsGrid() {
  const grid = document.getElementById("creatorsGrid");
  if (!grid) return;

  grid.innerHTML = "";
  appState.creators.forEach(c => {
    const card = document.createElement("div");
    card.className = "editorial-card rounded-lg p-6 space-y-4";
    card.innerHTML = `
      <div class="flex items-start justify-between">
        <div class="flex items-center gap-3">
          <div class="w-12 h-12 rounded bg-[#171717] text-white flex items-center justify-center font-serif text-xl font-bold">
            ${c.name.charAt(0)}
          </div>
          <div>
            <h3 class="font-serif text-xl font-bold text-[#171717]">${c.name}</h3>
            <p class="text-xs text-[#A68A5B] font-semibold">${c.handle}</p>
            <p class="text-xs text-[#696963] mt-0.5">${c.niche}</p>
          </div>
        </div>
        <div class="flex items-center gap-1.5">
          <button onclick="editCreator('${c.id}')" class="p-1.5 rounded hover:bg-[#F7F5F0] text-[#696963] hover:text-[#171717] transition" title="Edit Profile">
            <i data-lucide="edit-3" class="w-4 h-4"></i>
          </button>
          <button onclick="deleteCreator('${c.id}')" class="p-1.5 rounded hover:bg-red-50 text-[#696963] hover:text-red-600 transition" title="Delete Creator">
            <i data-lucide="trash" class="w-4 h-4"></i>
          </button>
        </div>
      </div>

      <div class="grid grid-cols-3 gap-2 py-3 px-3 bg-[#F7F5F0] rounded text-center border border-[#D9D6CE]">
        <div>
          <span class="block font-bold text-[#171717] text-sm">${c.followers}</span>
          <span class="text-[10px] text-[#696963] uppercase">Followers</span>
        </div>
        <div class="border-x border-[#D9D6CE]">
          <span class="block font-bold text-[#A68A5B] text-sm">${c.engagement_rate}</span>
          <span class="text-[10px] text-[#696963] uppercase">Engagement</span>
        </div>
        <div>
          <span class="block font-bold text-[#171717] text-sm">${c.avg_views}</span>
          <span class="text-[10px] text-[#696963] uppercase">Avg Views</span>
        </div>
      </div>

      <p class="text-xs text-[#696963] leading-relaxed italic border-l-2 border-[#A68A5B] pl-3">
        "${c.bio}"
      </p>

      <div class="space-y-1.5 text-xs text-[#696963]">
        <div><strong class="text-[#171717]">Target Brands:</strong> ${c.target_brands || "High Synergy"}</div>
        <div><strong class="text-[#171717]">Signature Angle:</strong> ${c.collab_angles || "Reel Feature"}</div>
        <div><strong class="text-[#171717]">Sample Rate:</strong> <span class="text-[#A68A5B] font-semibold">${c.sample_rate || "Flexible"}</span></div>
      </div>

      <div class="pt-3 flex items-center justify-between border-t border-[#D9D6CE]">
        <a href="${c.media_kit_url || '#'}" target="_blank" class="text-xs text-[#A68A5B] hover:text-[#171717] font-semibold flex items-center gap-1">
          <span>View Media Kit</span>
          <i data-lucide="arrow-up-right" class="w-3 h-3"></i>
        </a>
        <button onclick="selectCreatorForOutreach('${c.id}')" class="btn-editorial-dark text-[11px] px-3 py-1.5 rounded font-semibold">
          Create Campaign
        </button>
      </div>
    `;
    grid.appendChild(card);
  });

  if (window.lucide) lucide.createIcons();
}

function selectCreatorForOutreach(creatorId) {
  appState.selectedCreatorId = creatorId;
  const select = document.getElementById("studioCreatorSelect");
  if (select) select.value = creatorId;
  setCreatorMode("roster");
  onCreatorChange();
  switchTab("studio");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function insertPreset(promptText) {
  const area = document.getElementById("campaignPrompt");
  if (area) {
    area.value = promptText;
    area.focus();
  }
}

// --- LOCATION FILTER CONTROLLER ---
function selectLocationPreset(loc) {
  appState.selectedLocation = loc;
  const input = document.getElementById("campaignLocationInput");
  if (input) input.value = loc;

  // Update chip styles
  document.querySelectorAll(".location-chip-btn").forEach(btn => {
    const bLoc = btn.getAttribute("data-loc");
    if (bLoc === loc) {
      btn.className = "location-chip-btn active text-xs px-2.5 py-1 rounded-full border border-[#141413] bg-[#141413] text-[#FAF8F5] font-semibold transition";
    } else {
      btn.className = "location-chip-btn text-xs px-2.5 py-1 rounded-full border border-[#E2DDD2] bg-white text-[#383531] hover:border-[#141413] font-medium transition";
    }
  });
}

function handleCustomLocationInput(val) {
  const clean = val.trim();
  appState.selectedLocation = clean || "All India";

  // Match chip if exact
  document.querySelectorAll(".location-chip-btn").forEach(btn => {
    const bLoc = btn.getAttribute("data-loc");
    if (bLoc && bLoc.toLowerCase() === clean.toLowerCase()) {
      btn.className = "location-chip-btn active text-xs px-2.5 py-1 rounded-full border border-[#141413] bg-[#141413] text-[#FAF8F5] font-semibold transition";
    } else {
      btn.className = "location-chip-btn text-xs px-2.5 py-1 rounded-full border border-[#E2DDD2] bg-white text-[#383531] hover:border-[#141413] font-medium transition";
    }
  });
}

function toggleAutoPilotMode(enabled) {
  appState.isAutoPilot = enabled;
  const promptEl = document.getElementById("campaignPrompt");
  const chipsContainer = document.getElementById("presetChipsContainer");
  const statusLabel = document.getElementById("autoPilotStatusLabel");
  const btnText = document.getElementById("generateBtnText");

  if (enabled) {
    if (promptEl) {
      promptEl.disabled = true;
      promptEl.classList.add("opacity-60", "bg-gray-50");
      promptEl.dataset.prevVal = promptEl.value;
      promptEl.value = "🤖 [Autonomous Auto-Pilot Active] AI will autonomously inspect the selected creator profile, derive high-affinity brand categories, search the live web, crawl websites, and formulate bespoke video concepts.";
    }
    if (chipsContainer) chipsContainer.classList.add("opacity-40", "pointer-events-none");
    if (statusLabel) {
      statusLabel.innerText = "⚡ Auto-Pilot Active (Zero Interference)";
      statusLabel.className = "text-xs font-bold text-emerald-700";
    }
    if (btnText) btnText.innerText = "🚀 Launch Autonomous AI Campaign (Zero Interference)";
    showToast("Autonomous Auto-Pilot enabled! Click the button below to let AI handle everything autonomously.");
  } else {
    if (promptEl) {
      promptEl.disabled = false;
      promptEl.classList.remove("opacity-60", "bg-gray-50");
      promptEl.value = promptEl.dataset.prevVal || "";
    }
    if (chipsContainer) chipsContainer.classList.remove("opacity-40", "pointer-events-none");
    if (statusLabel) {
      statusLabel.innerText = "Manual Mode";
      statusLabel.className = "text-xs font-semibold text-[#66615B]";
    }
    updateGenerateButtonText();
  }
}

// --- GENERATE BRAND MATCHES & 3-PART BESPOKE PITCHES (STREAMING AGENT) ---
async function generatePitches() {
  const promptInput = document.getElementById("campaignPrompt");
  const prompt = promptInput ? promptInput.value.trim() : "";
  const emailStyle = document.getElementById("emailStyleSelect") ? document.getElementById("emailStyleSelect").value : "punchy";
  const countSelect = document.getElementById("brandCountSelect");
  const count = countSelect ? parseInt(countSelect.value) : 50;

  const locInput = document.getElementById("campaignLocationInput");
  const locationVal = (locInput ? locInput.value.trim() : "") || appState.selectedLocation || "All India";

  const part1Notes = document.getElementById("part1Notes")?.value.trim() || "";
  const part2Notes = document.getElementById("part2Notes")?.value.trim() || "";
  const part3Notes = document.getElementById("part3Notes")?.value.trim() || "";

  if (!appState.isAutoPilot && !prompt) {
    showToast("Please enter your brand discovery criteria first, or enable Auto-Pilot", false);
    if (promptInput) promptInput.focus();
    return;
  }

  // Pre-flight check: If Ollama is offline, open control modal
  if (!appState.ollamaRunning) {
    openOllamaControlModal();
    showToast("Ollama is currently offline. Please click 'Turn ON' in the control window.", false);
    return;
  }

  // Construct request payload
  const strictFilter = document.getElementById("strictOfficialFilter");
  const strictOfficial = strictFilter ? strictFilter.checked : true;
  const indianFilter = document.getElementById("indianOnlyFilter");
  const indianOnly = indianFilter ? indianFilter.checked : true;

  let payload = {
    prompt: appState.isAutoPilot ? "" : prompt,
    location: locationVal,
    email_style: emailStyle,
    count: count,
    video_idea: part2Notes,
    campaign_15day_notes: part3Notes,
    custom_instructions: part1Notes ? `About the Creator context:\n${part1Notes}` : "",
    ollama_model: appState.ollamaModel,
    strict_official_only: strictOfficial,
    indian_only: indianOnly
  };

  if (appState.creatorMode === "custom") {
    const customName = document.getElementById("customCreatorName").value.trim();
    const customHandle = document.getElementById("customCreatorHandle").value.trim();
    const customNiche = document.getElementById("customCreatorNiche").value.trim();
    const customFollowers = document.getElementById("customCreatorFollowers").value.trim();
    const customER = document.getElementById("customCreatorEngagement").value.trim();
    const customViews = document.getElementById("customCreatorViews").value.trim();
    const customBio = document.getElementById("customCreatorBio").value.trim();

    if (!customName || !customHandle) {
      showToast("Please provide at least a Creator Name and Handle for custom profile", false);
      return;
    }

    payload.custom_creator = {
      name: customName,
      handle: customHandle,
      niche: customNiche || "Lifestyle",
      followers: customFollowers || "50K",
      engagement_rate: customER || "5.0%",
      avg_views: customViews || "30K",
      bio: customBio || `Creator specializing in ${customNiche}`
    };
  } else {
    payload.creator_id = appState.selectedCreatorId;
  }

  const btn = document.getElementById("generateBtn");
  const btnText = document.getElementById("generateBtnText");
  const progressCard = document.getElementById("generationProgressCard");
  const progressBarFill = document.getElementById("progressBarFill");
  const progressPercent = document.getElementById("progressPercent");
  const progressTitle = document.getElementById("progressTitle");
  const progressSubtext = document.getElementById("progressSubtext");
  const progressBatchStep = document.getElementById("progressBatchStep");
  const consoleEl = document.getElementById("agentActivityConsole");
  const internetBadge = document.getElementById("internetStatusBadge");
  const internetText = document.getElementById("internetStatusText");

  btn.disabled = true;
  btnText.innerText = appState.isAutoPilot ? "Autonomous AI Agent Running..." : `Discovering & Pitching ${count} Brands...`;

  // Display and animate live progress card
  if (progressCard) {
    progressCard.classList.remove("hidden");
    if (progressBarFill) progressBarFill.style.width = "5%";
    if (progressPercent) progressPercent.innerText = "5%";
    if (progressTitle) progressTitle.innerText = appState.isAutoPilot ? "Autonomous AI Agent Formulating Campaign..." : `Searching Web & Ollama Discovering ${count} Brands...`;
    if (progressSubtext) progressSubtext.innerHTML = `<span>Initializing autonomous pipeline...</span>`;
    if (progressBatchStep) progressBatchStep.innerText = "Live Stream Active";
  }

  if (consoleEl) {
    consoleEl.innerHTML = `<div class="text-emerald-400 font-bold">[${new Date().toLocaleTimeString()}] 🤖 Autonomous AI Agent initialized. Target: ${count} brands. Project workspace secured.</div>`;
  }

  try {
    const res = await fetch("/api/agent/stream-discovery", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      throw new Error(`Server status ${res.status}: ${res.statusText}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let finalResult = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split("\n\n");
      buffer = frames.pop();

      for (const frame of frames) {
        const trimmed = frame.trim();
        if (!trimmed.startsWith("data: ")) continue;
        try {
          const item = JSON.parse(trimmed.slice(6));
          if (item.type === "event") {
            const ev = item.data;
            if (progressBarFill && ev.progress_pct) progressBarFill.style.width = `${ev.progress_pct}%`;
            if (progressPercent && ev.progress_pct) progressPercent.innerText = `${ev.progress_pct}%`;
            if (progressTitle && ev.title) progressTitle.innerText = ev.title;
            if (progressSubtext && ev.detail) progressSubtext.innerHTML = `<span>${ev.detail}</span>`;

            // Update live internet badge notification
            if (internetBadge && internetText) {
              if (ev.internet_active) {
                internetBadge.className = "flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300 transition-all duration-300";
                internetText.innerText = "🌐 LIVE INTERNET ACTIVE";
              } else {
                internetBadge.className = "flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-200 transition-all duration-300";
                internetText.innerText = `⚡ LOCAL OLLAMA (${appState.ollamaModel})`;
              }
            }

            // Append live console log entry
            if (consoleEl) {
              const colorClass = ev.internet_active ? "text-emerald-300" : (ev.stage === "ai_synthesis" ? "text-amber-300" : "text-gray-300");
              const icon = ev.internet_active ? "🌐" : (ev.stage === "ai_synthesis" ? "⚡" : "✓");
              const line = document.createElement("div");
              line.className = colorClass;
              line.innerText = `[${ev.timestamp}] ${icon} [${ev.stage.toUpperCase()}] ${ev.detail}`;
              consoleEl.appendChild(line);
              consoleEl.scrollTop = consoleEl.scrollHeight;
            }
          } else if (item.type === "complete") {
            finalResult = item.result;
          } else if (item.type === "error") {
            showToast("Agent error: " + item.message, false);
          }
        } catch (parseErr) {
          console.warn("Error parsing SSE frame:", parseErr);
        }
      }
    }

    if (finalResult && finalResult.brands && finalResult.brands.length > 0) {
      if (progressBarFill) progressBarFill.style.width = "100%";
      if (progressPercent) progressPercent.innerText = "100%";

      setTimeout(() => {
        if (progressCard) progressCard.classList.add("hidden");
      }, 800);

      appState.generatedBrands = finalResult.brands.map((b, i) => ({
        ...b,
        id: `brand_${Date.now()}_${i}`,
        creator_id: payload.creator_id || "custom",
        creator_name: payload.custom_creator ? payload.custom_creator.name : (appState.creators.find(c => c.id === payload.creator_id)?.name || "Creator")
      }));

      appState.selectedBrandIds = new Set(appState.generatedBrands.map(b => b.id));
      renderPitches(finalResult);
      await refreshBrandMemoryBadge();
      showToast(`Autonomous AI Agent completed! Discovered & formulated pitches for ${finalResult.brands.length} brands.`);

      // Smooth scroll to results
      const resultsSec = document.getElementById("resultsSection");
      if (resultsSec) {
        resultsSec.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    } else {
      if (progressCard) progressCard.classList.add("hidden");
      showToast((finalResult && finalResult.message) || "No brands found. Please refine criteria or creator profile.", false);
    }
  } catch (err) {
    if (progressCard) progressCard.classList.add("hidden");
    console.error("Agent error:", err);
    showToast("Autonomous discovery error: " + err.message, false);
  } finally {
    btn.disabled = false;
    updateGenerateButtonText();
  }
}

// --- RENDER GENERATED PITCH CARDS (WITH 3-PART BREAKDOWN & INTEGRATED VERIFICATION) ---
function renderPitches(data) {
  const section = document.getElementById("resultsSection");
  const list = document.getElementById("pitchesList");
  const summaryText = document.getElementById("resultsSummaryText");
  const countBadge = document.getElementById("brandResultCount");

  if (!section || !list) return;

  section.classList.remove("hidden");
  countBadge.innerText = `${appState.generatedBrands.length} Brands`;
  summaryText.innerText = data.summary || "Review your bespoke pitches below. Each pitch is structured with Crevanta's 3-part formula and verified against official Indian company records.";

  updateSelectedCountBadge();
  updateVerificationSummaryStrip();

  list.innerHTML = "";
  appState.generatedBrands.forEach((item, index) => {
    const card = document.createElement("div");
    card.id = `pitch-card-${item.id}`;
    card.className = "studio-module-card p-6 space-y-4 hover:shadow-lg transition duration-200";
    card.setAttribute("data-brand-name", (item.brand_name || "").toLowerCase());
    card.setAttribute("data-niche", (item.brand_niche || "").toLowerCase());
    card.setAttribute("data-domain", (item.website || "").toLowerCase());

    const isChecked = appState.selectedBrandIds.has(item.id);
    const bodyContent = item.full_email_body || item.body || "";
    const ev = item.email_verification || {};
    const isOfficial = (ev.status === "valid" || item.verification === "official") && item.recipient_email && item.recipient_email !== "Not publicly available";
    const emailVal = isOfficial ? item.recipient_email : (item.recipient_email || "Not publicly available");

    card.innerHTML = `
      <!-- TOP HEADER -->
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#E2DDD2]">
        <div class="flex items-center gap-3.5">
          <input type="checkbox" onchange="toggleBrandSelection('${item.id}', this.checked)" ${isChecked ? "checked" : ""} class="brand-select-check w-4 h-4 rounded border-[#E2DDD2] text-[#141413] focus:ring-0 cursor-pointer">
          <div>
            <div class="flex flex-wrap items-center gap-2.5">
              <span class="w-7 h-7 rounded-full bg-[#141413] text-[#FAF8F5] font-serif font-bold text-xs flex items-center justify-center shadow-sm">${index + 1}</span>
              <h4 class="font-serif text-xl font-bold text-[#141413]">${item.brand_name}</h4>
              <a href="https://${item.website}" target="_blank" class="text-xs text-[#B89248] hover:underline flex items-center gap-1 font-semibold">
                <span>${item.website}</span>
                <i data-lucide="arrow-up-right" class="w-3 h-3"></i>
              </a>
              <span class="text-[10px] uppercase font-bold px-2.5 py-0.5 rounded-full bg-[#FAF5EB] text-[#8F6F30] border border-[#E8D7B8]">${item.brand_niche || "Partner"}</span>
              <span class="text-[10px] uppercase font-bold px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-300 inline-flex items-center gap-1">
                <i data-lucide="map-pin" class="w-2.5 h-2.5 text-[#B89248]"></i>
                <span>${item.location || 'India'}</span>
              </span>
              <span class="text-[10px] uppercase font-bold px-2 py-0.5 rounded-full bg-blue-50 text-blue-800 border border-blue-200 inline-flex items-center gap-1">
                <i data-lucide="globe" class="w-2.5 h-2.5 text-blue-600"></i>
                <span>${item.search_source || 'Live Web Discovered'}</span>
              </span>
            </div>
            
            <!-- VERIFICATION LEVEL PILL & DELIVERABILITY SHIELD -->
            <div class="flex flex-wrap items-center gap-2 mt-2">
              <div id="status-badge-container-${item.id}" class="inline-flex flex-wrap items-center gap-2">
                ${renderCardVerificationBadge(ev, item)}
              </div>

              <!-- DELIVERABILITY SHIELD BADGE -->
              <span id="deliverability-badge-${item.id}" class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold ${(item.deliverability?.score || 100) >= 90 ? 'bg-emerald-50 text-emerald-800 border border-emerald-300' : 'bg-amber-50 text-amber-900 border border-amber-300'}">
                <i data-lucide="shield-check" class="w-3.5 h-3.5 text-emerald-600"></i>
                <span>${item.deliverability?.score || 100}% Primary Inbox</span>
              </span>

              <button onclick="sanitizeSinglePitch('${item.id}')" class="text-[11px] px-2.5 py-0.5 rounded bg-white hover:bg-[#FAF8F5] border border-[#E2DDD2] text-[#141413] font-medium inline-flex items-center gap-1 shadow-2xs hover:border-[#B89248] transition cursor-pointer" title="Auto-sanitize any spam words, optimize subject line, and append opt-out reputation shield">
                <i data-lucide="sparkles" class="w-3 h-3 text-[#B89248]"></i>
                <span>Auto-Sanitize</span>
              </button>
            </div>

            <!-- MULTI-STAGE VERIFICATION AUDIT PILLS -->
            <div id="stage-audit-container-${item.id}">
              ${renderStageAuditChecklist(ev, item)}
            </div>

            <p class="text-xs text-[#66615B] mt-2"><strong class="text-[#141413]">Strategic Fit:</strong> ${item.why_fit || "High demographic and aesthetic synergy with creator community."}</p>
          </div>
        </div>

        <!-- INDIVIDUAL ACTIONS -->
        <div class="flex items-center gap-2">
          <button onclick="actionPitch('${item.id}', 'draft')" class="btn-editorial-light text-xs px-3.5 py-1.5 rounded-md flex items-center gap-1.5 font-semibold shadow-sm" title="Save draft in Gmail">
            <i data-lucide="file-down" class="w-3.5 h-3.5 text-[#B89248]"></i>
            <span>Draft</span>
          </button>
          ${isOfficial ? `
            <button onclick="actionPitch('${item.id}', 'send')" id="send-btn-${item.id}" class="btn-editorial-dark text-xs px-4 py-1.5 rounded-md flex items-center gap-1.5 font-bold shadow-md" title="Send email live via Gmail">
              <i data-lucide="send" class="w-3.5 h-3.5 text-[#B89248]"></i>
              <span>Send Live</span>
            </button>
          ` : `
            <button onclick="showToast('Cannot send: No verified official email published by brand. Crevanta never sends to unverified or guessed addresses.', false)" id="send-btn-${item.id}" class="opacity-40 cursor-not-allowed bg-[#E2DDD2] text-[#66615B] text-xs px-4 py-1.5 rounded-md flex items-center gap-1.5 font-bold shadow-sm" title="Send locked: No verified official email published by brand.">
              <i data-lucide="lock" class="w-3.5 h-3.5"></i>
              <span>Send Locked</span>
            </button>
          `}
          <button onclick="removePitch('${item.id}')" class="p-1.5 text-[#66615B] hover:text-rose-600 transition" title="Discard">
            <i data-lucide="trash" class="w-4 h-4"></i>
          </button>
        </div>
      </div>

      <!-- RECIPIENT & SUBJECT -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <div class="flex items-center justify-between mb-1">
            <label class="block text-[11px] font-bold uppercase tracking-wider text-[#66615B]">Brand Contact Email (Zero Guessing):</label>
            <span class="text-[10px] text-[#8F6F30] font-semibold">Live SMTP Verification</span>
          </div>
          <div class="flex gap-2 items-center">
            <div class="relative flex-1">
              <input type="text" id="email-to-${item.id}" value="${emailVal}" class="w-full editorial-input px-3 py-2 rounded text-xs font-mono font-medium ${!isOfficial ? 'bg-amber-50/70 border-amber-300 text-amber-900' : ''}">
              ${!isOfficial ? `
                <span class="absolute right-2.5 top-1.5 text-[10px] uppercase font-bold text-amber-800 bg-amber-100 px-2 py-0.5 rounded border border-amber-200">Unverified</span>
              ` : ''}
            </div>
            <button onclick="verifySingleCardEmail('${item.id}')" id="verify-btn-${item.id}" class="btn-editorial-light text-xs px-3.5 py-2 rounded-lg font-bold flex items-center gap-1.5 shrink-0 shadow-2xs hover:border-[#B89248] transition" title="Run DNS, MX, and SMTP 250 handshake on this email live">
              <i data-lucide="shield-check" class="w-3.5 h-3.5 text-[#B89248]"></i>
              <span>Verify</span>
            </button>
          </div>
        </div>
        <div>
          <label class="block text-[11px] font-bold uppercase tracking-wider text-[#66615B] mb-1">Subject Line:</label>
          <input type="text" id="email-subject-${item.id}" value="${item.subject || ''}" class="w-full editorial-input px-3 py-2 rounded text-xs font-semibold">
        </div>
      </div>

      <!-- 3-PART EMAIL TABS -->
      <div class="space-y-2.5 pt-1">
        <div class="flex flex-wrap items-center gap-2">
          <button onclick="switchPitchSubTab('${item.id}', 'full')" id="subtab-full-${item.id}" class="email-part-pill active">Complete Email Body</button>
          <button onclick="switchPitchSubTab('${item.id}', 'part1')" id="subtab-part1-${item.id}" class="email-part-pill">1. About Creator</button>
          <button onclick="switchPitchSubTab('${item.id}', 'part2')" id="subtab-part2-${item.id}" class="email-part-pill">2. Unique Video Idea (4-Part)</button>
          <button onclick="switchPitchSubTab('${item.id}', 'part3')" id="subtab-part3-${item.id}" class="email-part-pill">3. 15-Day Campaign</button>
        </div>

        <!-- FULL EMAIL BODY TAB -->
        <div id="panel-full-${item.id}">
          <textarea id="email-body-${item.id}" rows="6" class="w-full editorial-input p-3.5 rounded-lg text-xs text-[#141413] leading-relaxed font-mono resize-y">${bodyContent}</textarea>
        </div>

        <!-- PART 1 PANEL -->
        <div id="panel-part1-${item.id}" class="hidden p-4 bg-[#FAF8F5] rounded-lg border border-[#E2DDD2] text-xs text-[#141413] leading-relaxed">
          <span class="text-[#8F6F30] font-bold uppercase tracking-wider block mb-1.5 text-[10px]">Part 1: About the Creator & Community Trust</span>
          ${item.part1_about_creator || "Introduces creator background, audience metrics, and community alignment."}
        </div>

        <!-- PART 2 PANEL (4-PART CREATIVE FORMULA BREAKDOWN) -->
        <div id="panel-part2-${item.id}" class="hidden p-4 bg-[#FAF8F5] rounded-lg border border-[#E2DDD2] space-y-3 text-xs text-[#141413] leading-relaxed">
          <div class="flex flex-wrap items-center justify-between gap-2 border-b border-[#E2DDD2] pb-2">
            <div class="flex items-center gap-2">
              <span class="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-[#141413] text-[#FAF8F5]">Campaign Concept</span>
              <h5 class="font-serif text-sm font-bold text-[#141413]">"${item.part2_concept_title || 'One Wardrobe, Three Occasions'}"</h5>
            </div>
            <span class="text-[10px] text-[#B89248] font-bold uppercase tracking-wider">Crevanta 4-Part Creative Formula</span>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
            <div class="bg-white p-3 rounded border border-[#E2DDD2]">
              <span class="text-[10px] font-bold uppercase tracking-wider text-[#8F6F30] block mb-1">1. Brand Insight (Differentiator)</span>
              <p class="text-xs text-[#141413]">${item.part2_brand_insight || item.why_fit || 'Brand offers high-taste craftsmanship in its category.'}</p>
            </div>
            <div class="bg-white p-3 rounded border border-[#E2DDD2]">
              <span class="text-[10px] font-bold uppercase tracking-wider text-[#8F6F30] block mb-1">2. Creative Opportunity</span>
              <p class="text-xs text-[#141413]">${item.part2_creative_opportunity || 'Integrating the product organically into authentic creator routines.'}</p>
            </div>
          </div>

          <div class="bg-white p-3 rounded border border-[#E2DDD2]">
            <span class="text-[10px] font-bold uppercase tracking-wider text-[#8F6F30] block mb-1">3. How It Works (Visual Hook & Creator Action)</span>
            <p class="text-xs text-[#141413]">${item.part2_how_it_works || item.part2_video_idea || 'Creator showcases the brand product in an engaging real-world format.'}</p>
          </div>
        </div>

        <!-- PART 3 PANEL -->
        <div id="panel-part3-${item.id}" class="hidden p-4 bg-[#FAF8F5] rounded-lg border border-[#E2DDD2] text-xs text-[#141413] leading-relaxed">
          <span class="text-[#8F6F30] font-bold uppercase tracking-wider block mb-1.5 text-[10px]">Part 3: Signature 15-Day Campaign Roadmap</span>
          ${item.part3_15day_campaign || "15-day structured workflow from kickoff to hero drop, interactive story dialogue, and analytics wrap."}
        </div>
      </div>
    `;
    list.appendChild(card);
  });

  if (window.lucide) lucide.createIcons();
}

// --- VERIFICATION HELPER RENDERING FUNCTIONS ---
function renderCardVerificationBadge(ev, item) {
  const isOfficial = (ev?.status === "valid" || item.verification === "official") && item.recipient_email && item.recipient_email !== "Not publicly available";
  if (ev?.status === "valid" || isOfficial) {
    return `
      <span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-300">
        <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
        <span>🟢 Official Email Verified · SMTP 250 OK</span>
      </span>
      <span class="text-[11px] text-[#66615B]">
        Source: <a href="${(item.email_source || '').startsWith('http') ? item.email_source : 'https://' + item.website}" target="_blank" class="text-[#B89248] hover:underline font-semibold">${item.email_source || 'Brand Official Website'}</a>
      </span>
    `;
  } else if (ev?.status === "catch-all") {
    return `
      <span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-50 text-amber-900 border border-amber-300">
        <span class="w-1.5 h-1.5 rounded-full bg-amber-500"></span>
        <span>⚠️ Catch-All Mailbox · Unverifiable</span>
      </span>
      <span class="text-[11px] text-[#8F6F30] italic">${ev.reason || 'Server accepts all addresses indiscriminately.'}</span>
    `;
  } else if (ev?.status === "disposable") {
    return `
      <span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-purple-50 text-purple-900 border border-purple-300">
        <span class="w-1.5 h-1.5 rounded-full bg-purple-500"></span>
        <span>🟣 Disposable Domain Blocked</span>
      </span>
    `;
  } else {
    return `
      <span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-rose-50 text-rose-900 border border-rose-300">
        <span class="w-1.5 h-1.5 rounded-full bg-rose-500"></span>
        <span>🔴 Not Publicly Listed</span>
      </span>
      <span class="text-[11px] text-[#8F6F30] italic">${item.email_source || 'Checked official site. No published email found.'}</span>
    `;
  }
}

function renderStageAuditChecklist(ev, item) {
  const isIndian = ev?.is_indian !== false && item?.is_indian !== false;
  const isDnsOk = ev?.stages?.dns_existence?.passed !== false;
  const mxHost = ev?.mx_host ? (ev.mx_host.length > 22 ? ev.mx_host.substring(0, 20) + '...' : ev.mx_host) : 'Verified';
  const isSmtpOk = ev?.status === "valid" || (item?.verification === "official" && ev?.status !== "catch-all");
  const isCatchAll = ev?.status === "catch-all" || ev?.is_catch_all;

  return `
    <div class="flex flex-wrap items-center gap-1.5 mt-2 text-[10px] font-medium text-[#66615B]">
      <span class="px-2 py-0.5 rounded bg-white border border-[#E2DDD2] flex items-center gap-1 ${isIndian ? 'text-emerald-800' : 'text-rose-800'}">
        <i data-lucide="${isIndian ? 'check-circle' : 'x-circle'}" class="w-3 h-3 ${isIndian ? 'text-emerald-600' : 'text-rose-600'}"></i>
        <span>Indian Entity 🇮🇳</span>
      </span>
      <span class="px-2 py-0.5 rounded bg-white border border-[#E2DDD2] flex items-center gap-1 ${isDnsOk ? 'text-emerald-800' : 'text-rose-800'}">
        <i data-lucide="${isDnsOk ? 'check-circle' : 'x-circle'}" class="w-3 h-3 ${isDnsOk ? 'text-emerald-600' : 'text-rose-600'}"></i>
        <span>DNS A/AAAA</span>
      </span>
      <span class="px-2 py-0.5 rounded bg-white border border-[#E2DDD2] flex items-center gap-1 text-emerald-800">
        <i data-lucide="check-circle" class="w-3 h-3 text-emerald-600"></i>
        <span>MX: ${mxHost}</span>
      </span>
      <span class="px-2 py-0.5 rounded bg-white border border-[#E2DDD2] flex items-center gap-1 ${isSmtpOk ? 'text-emerald-800' : (isCatchAll ? 'text-amber-800' : 'text-rose-800')}">
        <i data-lucide="${isSmtpOk ? 'check-circle' : (isCatchAll ? 'alert-triangle' : 'x-circle')}" class="w-3 h-3 ${isSmtpOk ? 'text-emerald-600' : (isCatchAll ? 'text-amber-600' : 'text-rose-600')}"></i>
        <span>${isSmtpOk ? 'SMTP 250 Handshake OK' : (isCatchAll ? 'Catch-All Mailbox' : 'Unverified SMTP')}</span>
      </span>
      <span class="px-2 py-0.5 rounded bg-white border border-[#E2DDD2] flex items-center gap-1 text-emerald-800">
        <i data-lucide="check-circle" class="w-3 h-3 text-emerald-600"></i>
        <span>Anti-Spam Shield</span>
      </span>
    </div>
  `;
}

function updateVerificationSummaryStrip() {
  const totalEl = document.getElementById("summaryTotalBrands");
  const validEl = document.getElementById("summaryValidMailboxes");
  const catchAllEl = document.getElementById("summaryCatchAll");
  const indianEl = document.getElementById("summaryIndianEntities");
  const delivEl = document.getElementById("summaryAvgDeliverability");

  if (!totalEl) return;

  const brands = appState.generatedBrands || [];
  const total = brands.length;
  let validCount = 0;
  let catchAllCount = 0;
  let indianCount = 0;
  let totalScore = 0;

  brands.forEach(b => {
    const ev = b.email_verification || {};
    const isValid = ev.status === "valid" || (b.verification === "official" && b.recipient_email && b.recipient_email !== "Not publicly available");
    if (isValid) validCount++;
    if (ev.status === "catch-all" || ev.is_catch_all) catchAllCount++;
    if (b.is_indian !== false && ev.is_indian !== false) indianCount++;
    totalScore += (b.deliverability?.score || 100);
  });

  const avgScore = total > 0 ? Math.round(totalScore / total) : 100;

  totalEl.innerText = total;
  if (validEl) validEl.innerText = validCount;
  if (catchAllEl) catchAllEl.innerText = catchAllCount;
  if (indianEl) indianEl.innerText = indianCount;
  if (delivEl) delivEl.innerText = `${avgScore}%`;
}

// --- LIVE INLINE CARD EMAIL VERIFICATION ---
async function verifySingleCardEmail(brandId) {
  const brand = appState.generatedBrands.find(b => b.id === brandId);
  if (!brand) return;

  const emailInput = document.getElementById(`email-to-${brandId}`);
  const targetEmail = emailInput ? emailInput.value.trim() : (brand.recipient_email || "");
  const btn = document.getElementById(`verify-btn-${brandId}`);
  const statusContainer = document.getElementById(`status-badge-container-${brandId}`);
  const stageAuditContainer = document.getElementById(`stage-audit-container-${brandId}`);
  const sendBtn = document.getElementById(`send-btn-${brandId}`);

  if (!targetEmail || targetEmail === "Not publicly available") {
    showToast("Please enter an email address to verify", false);
    return;
  }

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span class="animate-spin mr-1">⏳</span> Checking...`;
  }

  try {
    const res = await fetch("/api/email-verifier/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email_or_domain: targetEmail,
        brand_name: brand.brand_name,
        check_indian_only: true,
        force_recheck: true
      })
    });

    const data = await res.json();
    brand.email_verification = data;
    brand.recipient_email = targetEmail;

    if (data.approved && data.status === "valid") {
      brand.verification = "official";
      if (statusContainer) statusContainer.innerHTML = renderCardVerificationBadge(data, brand);
      if (stageAuditContainer) stageAuditContainer.innerHTML = renderStageAuditChecklist(data, brand);
      if (emailInput) {
        emailInput.className = "w-full editorial-input px-3 py-2 rounded text-xs font-mono font-medium";
      }
      if (sendBtn) {
        sendBtn.disabled = false;
        sendBtn.className = "btn-editorial-dark text-xs px-4 py-1.5 rounded-md flex items-center gap-1.5 font-bold shadow-md";
        sendBtn.title = "Send email live via Gmail";
        sendBtn.onclick = () => actionPitch(brandId, "send");
        sendBtn.innerHTML = `<i data-lucide="send" class="w-3.5 h-3.5 text-[#B89248]"></i><span>Send Live</span>`;
      }
      showToast(`✓ Verified! Mailbox for ${brand.brand_name} exists & passed SMTP 250 handshake.`);
    } else if (data.status === "catch-all") {
      brand.verification = "catch-all";
      if (statusContainer) statusContainer.innerHTML = renderCardVerificationBadge(data, brand);
      if (stageAuditContainer) stageAuditContainer.innerHTML = renderStageAuditChecklist(data, brand);
      showToast(`Notice: ${brand.brand_name} is a Catch-All mailbox (unverifiable).`, false);
    } else {
      brand.verification = "unverified";
      if (statusContainer) statusContainer.innerHTML = renderCardVerificationBadge(data, brand);
      if (stageAuditContainer) stageAuditContainer.innerHTML = renderStageAuditChecklist(data, brand);
      if (sendBtn) {
        sendBtn.disabled = true;
        sendBtn.className = "opacity-40 cursor-not-allowed bg-[#E2DDD2] text-[#66615B] text-xs px-4 py-1.5 rounded-md flex items-center gap-1.5 font-bold shadow-sm";
        sendBtn.title = `Send locked: ${data.reason || 'Email not verified'}`;
        sendBtn.onclick = () => showToast(`Cannot send: ${data.reason || 'Email not verified'}`, false);
        sendBtn.innerHTML = `<i data-lucide="lock" class="w-3.5 h-3.5"></i><span>Send Locked</span>`;
      }
      showToast(`Verification issue: ${data.reason || data.status}`, false);
    }

    updateVerificationSummaryStrip();
    if (window.lucide) lucide.createIcons();
  } catch (err) {
    showToast("Verification check failed: " + err.message, false);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<i data-lucide="shield-check" class="w-3.5 h-3.5 text-[#B89248]"></i><span>Verify</span>`;
      if (window.lucide) lucide.createIcons();
    }
  }
}

function switchPitchSubTab(pitchId, subtab) {
  const tabs = ["full", "part1", "part2", "part3"];
  tabs.forEach(t => {
    const btn = document.getElementById(`subtab-${t}-${pitchId}`);
    const panel = document.getElementById(`panel-${t}-${pitchId}`);
    if (btn && panel) {
      if (t === subtab) {
        btn.classList.add("active");
        panel.classList.remove("hidden");
      } else {
        btn.classList.remove("active");
        panel.classList.add("hidden");
      }
    }
  });
}

function toggleBrandSelection(id, isChecked) {
  if (isChecked) {
    appState.selectedBrandIds.add(id);
  } else {
    appState.selectedBrandIds.delete(id);
  }
  updateSelectedCountBadge();
}

function toggleSelectAllBrands(selectAll) {
  const checkboxes = document.querySelectorAll(".brand-select-check");
  checkboxes.forEach(cb => {
    cb.checked = selectAll;
  });

  if (selectAll) {
    appState.selectedBrandIds = new Set(appState.generatedBrands.map(b => b.id));
  } else {
    appState.selectedBrandIds.clear();
  }
  updateSelectedCountBadge();
}

function updateSelectedCountBadge() {
  const badge = document.getElementById("selectedCountBadge");
  if (badge) badge.innerText = appState.selectedBrandIds.size;

  const btnSendText = document.getElementById("btnSendAllText");
  if (btnSendText) {
    btnSendText.innerText = `1-Click Send All (${appState.selectedBrandIds.size})`;
  }

  const btnDraftText = document.getElementById("btnDraftAllText");
  if (btnDraftText) {
    btnDraftText.innerText = `1-Click Draft All (${appState.selectedBrandIds.size})`;
  }
}

function filterBrandCards() {
  const searchInput = document.getElementById("brandSearchInput");
  const query = (searchInput ? searchInput.value : "").toLowerCase().trim();
  const cards = document.querySelectorAll("#pitchesList > div");

  cards.forEach(card => {
    const name = card.getAttribute("data-brand-name") || "";
    const niche = card.getAttribute("data-niche") || "";
    const domain = card.getAttribute("data-domain") || "";
    if (!query || name.includes(query) || niche.includes(query) || domain.includes(query)) {
      card.classList.remove("hidden");
    } else {
      card.classList.add("hidden");
    }
  });
}

function removePitch(id) {
  appState.generatedBrands = appState.generatedBrands.filter(b => b.id !== id);
  appState.selectedBrandIds.delete(id);
  const card = document.getElementById(`pitch-card-${id}`);
  if (card) card.remove();

  const countBadge = document.getElementById("brandResultCount");
  if (countBadge) countBadge.innerText = `${appState.generatedBrands.length} Brands`;
  updateSelectedCountBadge();

  if (appState.generatedBrands.length === 0) {
    document.getElementById("resultsSection").classList.add("hidden");
  }
}

// --- SINGLE PITCH ACTION (SEND OR DRAFT) ---
async function actionPitch(id, mode) {
  const brand = appState.generatedBrands.find(b => b.id === id);
  if (!brand) return;

  const toEmail = document.getElementById(`email-to-${id}`).value.trim();
  const subject = document.getElementById(`email-subject-${id}`).value.trim();
  const body = document.getElementById(`email-body-${id}`).value.trim();

  if (!toEmail) {
    showToast("Please provide a recipient email address", false);
    return;
  }

  const endpoint = mode === "draft" ? "/api/email/draft" : "/api/email/send";
  try {
    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        to_email: toEmail,
        subject: subject,
        body: body,
        creator_name: brand.creator_name || "",
        brand_name: brand.brand_name
      })
    });
    const result = await res.json();
    if (result.success) {
      showToast(result.message || (mode === "draft" ? "Draft saved into Gmail!" : "Email sent live!"));
      await loadHistory();
    } else {
      showToast(result.message || "Action failed. Check Gmail credentials.", false);
    }
  } catch (err) {
    showToast("Error: " + err.message, false);
  }
}

// --- EXPLICIT USER CONFIRMATION FOR 1-CLICK BATCH DISPATCH ---
function requestBatchConfirmation(mode) {
  const selectedBrands = appState.generatedBrands.filter(b => appState.selectedBrandIds.has(b.id));
  if (selectedBrands.length === 0) {
    showToast("Please select at least one brand first", false);
    return;
  }

  appState.pendingDispatchMode = mode;

  const modal = document.getElementById("dispatchConfirmModal");
  const countSpan = document.getElementById("confirmSelectedCount");
  const modeSpan = document.getElementById("confirmExecutionMode");
  const warningBox = document.getElementById("confirmWarningBox");
  const btn = document.getElementById("confirmDispatchBtn");
  const pacingSelect = document.getElementById("confirmPacingMode");

  countSpan.innerText = selectedBrands.length;
  if (mode === "draft") {
    modeSpan.innerText = "SAVE DRAFTS (IMAP)";
    if (pacingSelect) pacingSelect.value = "drafts";
    warningBox.innerHTML = `<strong>Note:</strong> Pitches will be saved directly into your connected Gmail Drafts folder without sending. You can inspect each draft inside Gmail.`;
    btn.innerText = `Confirm & Draft ${selectedBrands.length} Pitches`;
  } else {
    modeSpan.innerText = "SEND LIVE (SMTP)";
    if (pacingSelect) pacingSelect.value = "human_safe";
    warningBox.innerHTML = `<strong>Important:</strong> ${selectedBrands.length} emails will be delivered live with Anti-Spam Human Jitter pacing (20–35s delay) to guarantee Primary Inbox delivery and protect your sender reputation.`;
    btn.innerText = `Confirm & Send ${selectedBrands.length} Live Emails`;
  }

  modal.classList.remove("hidden");
  if (window.lucide) lucide.createIcons();
}

function closeDispatchConfirmModal() {
  const modal = document.getElementById("dispatchConfirmModal");
  if (modal) modal.classList.add("hidden");
}

async function executeConfirmedBulk() {
  const pacingMode = document.getElementById("confirmPacingMode")?.value || (appState.pendingDispatchMode === "draft" ? "drafts" : "human_safe");
  closeDispatchConfirmModal();
  const mode = appState.pendingDispatchMode;
  const selectedBrands = appState.generatedBrands.filter(b => appState.selectedBrandIds.has(b.id));
  if (selectedBrands.length === 0) return;

  const pitchesPayload = selectedBrands.map(b => {
    return {
      recipient_email: document.getElementById(`email-to-${b.id}`).value.trim(),
      subject: document.getElementById(`email-subject-${b.id}`).value.trim(),
      body: document.getElementById(`email-body-${b.id}`).value.trim(),
      brand_name: b.brand_name,
      creator_name: b.creator_name || ""
    };
  });

  openBulkProgressModal(selectedBrands.length, mode);

  try {
    const res = await fetch("/api/email/bulk-job", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        pitches: pitchesPayload,
        mode: mode,
        delay_seconds: mode === "draft" ? 1.0 : 0.75,
        pacing_mode: pacingMode
      })
    });

    const jobData = await res.json();
    appState.activeBulkJobId = jobData.job_id;

    // Start polling job status
    appState.bulkPollInterval = setInterval(() => pollBulkJob(jobData.job_id), 600);
  } catch (err) {
    showToast("Failed to initiate batch job: " + err.message, false);
    closeBulkProgressModal();
  }
}

// --- 1-CLICK BULK PROGRESS POLLER ---
function openBulkProgressModal(total, mode) {
  const modal = document.getElementById("bulkProgressModal");
  const title = document.getElementById("bulkModalTitle");
  const badge = document.getElementById("bulkStatusBadge");
  const label = document.getElementById("bulkProgressLabel");
  const percent = document.getElementById("bulkProgressPercent");
  const bar = document.getElementById("bulkProgressBar");
  const brand = document.getElementById("bulkCurrentBrand");
  const feed = document.getElementById("bulkActivityFeed");
  const closeBtn = document.getElementById("bulkCloseBtn");
  const cancelBtn = document.getElementById("bulkCancelBtn");
  const doneBtn = document.getElementById("bulkDoneBtn");
  const pacingNote = document.getElementById("bulkPacingNoteText");

  modal.classList.remove("hidden");
  title.innerText = mode === "draft" ? "1-Click Bulk Gmail Drafter" : "1-Click Bulk Gmail Dispatcher (Anti-Spam)";
  badge.className = "editorial-badge badge-active";
  badge.innerText = "Active";
  label.innerText = `Progress: 0 / ${total}`;
  percent.innerText = "0%";
  bar.style.width = "0%";
  brand.innerText = "Initializing live connection...";
  feed.innerHTML = `<div class="text-[#696963]">Job initialized. Applying anti-spam deliverability protection...</div>`;
  if (pacingNote) pacingNote.innerText = "Starting deliverability-safe dispatch with human cadence...";

  closeBtn.classList.add("hidden");
  cancelBtn.classList.remove("hidden");
  doneBtn.classList.add("hidden");

  if (window.lucide) lucide.createIcons();
}

async function pollBulkJob(jobId) {
  try {
    const res = await fetch(`/api/email/bulk-job/${jobId}`);
    if (!res.ok) return;

    const job = await res.json();
    const label = document.getElementById("bulkProgressLabel");
    const percent = document.getElementById("bulkProgressPercent");
    const bar = document.getElementById("bulkProgressBar");
    const brand = document.getElementById("bulkCurrentBrand");
    const feed = document.getElementById("bulkActivityFeed");
    const badge = document.getElementById("bulkStatusBadge");
    const closeBtn = document.getElementById("bulkCloseBtn");
    const cancelBtn = document.getElementById("bulkCancelBtn");
    const doneBtn = document.getElementById("bulkDoneBtn");
    const pacingNote = document.getElementById("bulkPacingNoteText");

    const pct = Math.round((job.completed / Math.max(1, job.total)) * 100);
    label.innerText = `Progress: ${job.completed} / ${job.total} (Success: ${job.success_count}, Failed: ${job.failed_count})`;
    percent.innerText = `${pct}%`;
    bar.style.width = `${pct}%`;
    brand.innerText = job.current_brand || "Processing...";

    if (job.pacing_note && pacingNote) {
      pacingNote.innerText = job.pacing_note;
    }

    if (job.logs && job.logs.length > 0) {
      feed.innerHTML = job.logs.map(l => {
        const isOk = l.status === "delivered";
        const color = isOk ? "text-[#2E7D32]" : "text-rose-600";
        return `<div><span class="${color}">[${l.status.toUpperCase()}]</span> <strong>${l.brand_name}</strong> &lt;${l.to_email}&gt; — <span class="text-[#696963]">${l.message}</span></div>`;
      }).join("");
      feed.scrollTop = feed.scrollHeight;
    }

    if (job.status === "completed" || job.status === "cancelled") {
      clearInterval(appState.bulkPollInterval);
      appState.bulkPollInterval = null;

      badge.className = job.status === "completed" ? "editorial-badge badge-active" : "editorial-badge badge-warning";
      badge.innerText = job.status === "completed" ? "Completed" : "Stopped";

      cancelBtn.classList.add("hidden");
      closeBtn.classList.remove("hidden");
      doneBtn.classList.remove("hidden");

      await loadHistory();
      showToast(job.status === "completed" ? `Batch complete! ${job.success_count} emails processed.` : "Batch dispatch cancelled.");
    }
  } catch (err) {
    console.error("Poll error:", err);
  }
}

async function cancelBulkJobAction() {
  if (!appState.activeBulkJobId) return;
  try {
    await fetch(`/api/email/bulk-job/${appState.activeBulkJobId}/cancel`, { method: "POST" });
    showToast("Sent stop request to bulk job runner.");
  } catch (err) {
    showToast("Error stopping job: " + err.message, false);
  }
}

function finishBulkJob() {
  closeBulkProgressModal();
  switchTab("history");
}

function closeBulkProgressModal() {
  const modal = document.getElementById("bulkProgressModal");
  if (modal) modal.classList.add("hidden");
  if (appState.bulkPollInterval) {
    clearInterval(appState.bulkPollInterval);
    appState.bulkPollInterval = null;
  }
}

// --- OLLAMA AI STRATEGIST CHAT & TALK RECORDS ---
async function loadTalks() {
  try {
    const res = await fetch("/api/talks");
    appState.talks = await res.json();
    renderTalksList();

    if (appState.talks.length > 0 && !appState.activeTalkId) {
      selectTalk(appState.talks[0].id);
    } else if (!appState.activeTalkId) {
      startNewTalk();
    }
  } catch (err) {
    console.error("Failed to load talks:", err);
  }
}

function renderTalksList() {
  const list = document.getElementById("talksList");
  const countBadge = document.getElementById("talksCountBadge");
  if (!list) return;

  if (countBadge) {
    countBadge.innerText = `${appState.talks.length} ${appState.talks.length === 1 ? 'talk' : 'talks'}`;
  }

  list.innerHTML = "";
  if (appState.talks.length === 0) {
    list.innerHTML = `
      <div class="p-6 text-center text-xs text-[#696963]">
        <i data-lucide="message-square" class="w-6 h-6 mx-auto mb-2 opacity-40"></i>
        No recorded talks yet.<br>Click <strong>+ New Talk</strong> or send a message to record conversations.
      </div>
    `;
    if (window.lucide) lucide.createIcons();
    return;
  }

  appState.talks.forEach(t => {
    const isActive = t.id === appState.activeTalkId;
    const item = document.createElement("div");
    item.className = `p-3.5 transition cursor-pointer flex items-start justify-between gap-2.5 ${isActive ? 'bg-white border-l-4 border-l-[#171717] shadow-sm' : 'hover:bg-white/60'}`;
    item.onclick = () => selectTalk(t.id);

    const dateStr = t.updated_at ? new Date(t.updated_at).toLocaleDateString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "Recent";
    const msgCount = (t.messages || []).length;

    item.innerHTML = `
      <div class="min-w-0 flex-1">
        <div class="font-bold text-xs text-[#171717] truncate">${t.title || "Strategic Conversation"}</div>
        <div class="flex items-center gap-2 mt-1 text-[10px] text-[#696963]">
          <span class="truncate max-w-[120px] text-[#A68A5B] font-semibold">${t.creator_name || "General"}</span>
          <span>·</span>
          <span>${dateStr}</span>
          <span>·</span>
          <span>${msgCount} msgs</span>
        </div>
      </div>
      <button onclick="deleteTalkAction('${t.id}', event)" class="p-1 rounded text-[#696963] hover:text-red-600 hover:bg-red-50 transition" title="Delete Talk">
        <i data-lucide="trash" class="w-3.5 h-3.5"></i>
      </button>
    `;
    list.appendChild(item);
  });

  if (window.lucide) lucide.createIcons();
}

function selectTalk(sessionId) {
  const talk = appState.talks.find(t => t.id === sessionId);
  if (!talk) return;

  appState.activeTalkId = sessionId;
  appState.chatMessages = talk.messages || [];

  const titleEl = document.getElementById("activeTalkTitle");
  const metaEl = document.getElementById("activeTalkMeta");
  const badgeEl = document.getElementById("activeTalkCreatorBadge");

  if (titleEl) titleEl.innerText = talk.title || "Strategic Conversation";
  if (metaEl) {
    const updatedStr = talk.updated_at ? new Date(talk.updated_at).toLocaleString() : "Recently active";
    metaEl.innerText = `Recorded session · Last active ${updatedStr}`;
  }
  if (badgeEl) badgeEl.innerText = talk.creator_name || "General Strategy";

  renderChatMessages();
  renderTalksList();
}

function startNewTalk() {
  appState.activeTalkId = null;
  const creator = appState.creators.find(c => c.id === appState.selectedCreatorId);
  const creatorName = creator ? creator.name : "General Strategy";

  const titleEl = document.getElementById("activeTalkTitle");
  const metaEl = document.getElementById("activeTalkMeta");
  const badgeEl = document.getElementById("activeTalkCreatorBadge");

  if (titleEl) titleEl.innerText = "New Strategic Session";
  if (metaEl) metaEl.innerText = "Powered by local Ollama AI · Private & Free";
  if (badgeEl) badgeEl.innerText = creatorName;

  appState.chatMessages = [
    {
      role: "assistant",
      content: `Hello! I am your Crevanta Brand Partnerships Strategist, running locally on your Mac via Ollama (${appState.ollamaModel}). How can I help you brainstorm collaboration angles, pitch hooks, or 15-day campaign milestones today?`
    }
  ];

  renderChatMessages();
  renderTalksList();
}

async function deleteTalkAction(sessionId, event) {
  if (event) event.stopPropagation();
  try {
    await fetch(`/api/talks/${sessionId}`, { method: "DELETE" });
    appState.talks = appState.talks.filter(t => t.id !== sessionId);
    if (appState.activeTalkId === sessionId) {
      if (appState.talks.length > 0) {
        selectTalk(appState.talks[0].id);
      } else {
        startNewTalk();
      }
    } else {
      renderTalksList();
    }
    showToast("Talk record removed.");
  } catch (err) {
    showToast("Failed to delete talk: " + err.message, false);
  }
}

async function clearAllTalksAction() {
  if (!confirm("Are you sure you want to delete all saved talk history?")) return;
  try {
    await fetch("/api/talks", { method: "DELETE" });
    appState.talks = [];
    startNewTalk();
    showToast("All talk records cleared.");
  } catch (err) {
    showToast("Failed to clear talks: " + err.message, false);
  }
}

function renderChatMessages() {
  const stream = document.getElementById("chatStream");
  if (!stream) return;

  stream.innerHTML = "";
  appState.chatMessages.forEach(m => {
    const isUser = m.role === "user";
    const div = document.createElement("div");
    div.className = `flex ${isUser ? "justify-end" : "justify-start"}`;

    div.innerHTML = `
      <div class="max-w-xl rounded-lg p-4 text-xs leading-relaxed ${isUser ? "bg-[#171717] text-[#F7F5F0]" : "bg-white border border-[#D9D6CE] text-[#171717] shadow-sm"}">
        <div class="font-bold text-[10px] uppercase tracking-wider mb-1 ${isUser ? "text-[#A68A5B]" : "text-[#696963]"}">
          ${isUser ? "You" : `Ollama AI (${appState.ollamaModel})`}
        </div>
        <div class="whitespace-pre-wrap">${m.content}</div>
      </div>
    `;
    stream.appendChild(div);
  });

  stream.scrollTop = stream.scrollHeight;
  if (window.lucide) lucide.createIcons();
}

async function sendChatMessage() {
  const input = document.getElementById("chatInput");
  const msg = input ? input.value.trim() : "";
  if (!msg) return;

  appState.chatMessages.push({ role: "user", content: msg });
  input.value = "";
  renderChatMessages();

  const stream = document.getElementById("chatStream");
  const typingDiv = document.createElement("div");
  typingDiv.className = "flex justify-start";
  typingDiv.id = "chatTypingIndicator";
  typingDiv.innerHTML = `
    <div class="max-w-xl rounded-lg p-3 text-xs bg-white border border-[#D9D6CE] text-[#696963] shadow-sm flex items-center gap-2">
      <div class="w-2 h-2 rounded-full bg-[#A68A5B] animate-ping"></div>
      <span>Ollama is thinking...</span>
    </div>
  `;
  if (stream) {
    stream.appendChild(typingDiv);
    stream.scrollTop = stream.scrollHeight;
  }

  const btn = document.getElementById("chatSendBtn");
  if (btn) btn.disabled = true;

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: appState.chatMessages.filter(m => m.role === "user" || m.role === "assistant"),
        session_id: appState.activeTalkId,
        creator_id: appState.selectedCreatorId,
        ollama_model: appState.ollamaModel
      })
    });

    const indicator = document.getElementById("chatTypingIndicator");
    if (indicator) indicator.remove();

    const data = await res.json();
    if (data.reply) {
      appState.chatMessages.push({ role: "assistant", content: data.reply });
      if (data.session_id) {
        appState.activeTalkId = data.session_id;
      }
      // Refresh talks list to update session title & metadata
      const talksRes = await fetch("/api/talks");
      appState.talks = await talksRes.json();
      renderTalksList();
    } else if (data.message) {
      appState.chatMessages.push({ role: "assistant", content: data.message });
    }
  } catch (err) {
    const indicator = document.getElementById("chatTypingIndicator");
    if (indicator) indicator.remove();
    appState.chatMessages.push({ role: "assistant", content: "Error: " + err.message });
  } finally {
    if (btn) btn.disabled = false;
    renderChatMessages();
  }
}

// --- SAVED COMMANDS / PLAYBOOK ---
async function loadCommands() {
  try {
    const res = await fetch("/api/commands");
    appState.savedCommands = await res.json();
    renderPlaybook();
  } catch (err) {
    console.error("Failed to load commands:", err);
  }
}

function renderPlaybook() {
  const grid = document.getElementById("playbookGrid");
  if (!grid) return;

  grid.innerHTML = "";
  if (appState.savedCommands.length === 0) {
    grid.innerHTML = `
      <div class="col-span-3 text-center py-12 text-xs text-[#696963]">
        No saved commands yet. Click "Save Prompt to Playbook" in Campaign Studio to create templates.
      </div>
    `;
    return;
  }

  appState.savedCommands.forEach(cmd => {
    const card = document.createElement("div");
    card.className = "editorial-card rounded-lg p-5 space-y-3";
    card.innerHTML = `
      <div class="flex items-start justify-between">
        <h4 class="font-serif text-lg font-bold text-[#171717]">${cmd.name || "Custom Playbook"}</h4>
        <button onclick="deleteCommandAction('${cmd.id}')" class="text-[#696963] hover:text-red-600 transition" title="Delete Playbook">
          <i data-lucide="trash" class="w-4 h-4"></i>
        </button>
      </div>
      <p class="text-xs text-[#696963] line-clamp-3 italic">"${cmd.prompt}"</p>
      <div class="flex items-center justify-between pt-2 border-t border-[#D9D6CE]">
        <span class="text-[10px] uppercase font-bold text-[#A68A5B]">Style: ${cmd.email_style || "Punchy"}</span>
        <button onclick="executeSavedCommand('${cmd.id}')" class="btn-editorial-dark text-[11px] px-3 py-1 rounded font-semibold">
          Load & Run
        </button>
      </div>
    `;
    grid.appendChild(card);
  });

  if (window.lucide) lucide.createIcons();
}

async function saveCurrentCommand() {
  const prompt = document.getElementById("campaignPrompt")?.value.trim();
  if (!prompt) {
    showToast("Please enter a command prompt first", false);
    return;
  }

  const name = prompt.length > 35 ? prompt.substring(0, 35) + "..." : prompt;
  const emailStyle = document.getElementById("emailStyleSelect")?.value || "punchy";

  try {
    const res = await fetch("/api/commands", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: name,
        prompt: prompt,
        email_style: emailStyle
      })
    });
    const saved = await res.json();
    appState.savedCommands.push(saved);
    renderPlaybook();
    showToast("Command saved into your Playbook!");
  } catch (err) {
    showToast("Failed to save command: " + err.message, false);
  }
}

function executeSavedCommand(id) {
  const cmd = appState.savedCommands.find(c => c.id === id);
  if (!cmd) return;

  const promptInput = document.getElementById("campaignPrompt");
  const styleSelect = document.getElementById("emailStyleSelect");
  if (promptInput) promptInput.value = cmd.prompt;
  if (styleSelect && cmd.email_style) styleSelect.value = cmd.email_style;

  switchTab("studio");
  window.scrollTo({ top: 0, behavior: "smooth" });
  showToast("Loaded command from Playbook. Ready to discover!");
}

async function deleteCommandAction(id) {
  try {
    await fetch(`/api/commands/${id}`, { method: "DELETE" });
    appState.savedCommands = appState.savedCommands.filter(c => c.id !== id);
    renderPlaybook();
    showToast("Command deleted from Playbook.");
  } catch (err) {
    showToast("Failed to delete command: " + err.message, false);
  }
}

// --- OUTREACH AUDIT LOG ---
async function loadHistory() {
  try {
    const res = await fetch("/api/history");
    appState.history = await res.json();
    renderHistoryTable();
  } catch (err) {
    console.error("Failed to load history:", err);
  }
}

function renderHistoryTable() {
  const tbody = document.getElementById("historyTableBody");
  if (!tbody) return;

  tbody.innerHTML = "";
  if (appState.history.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="6" class="p-8 text-center text-xs text-[#696963]">
          No outreach recorded yet. Emails sent or drafted via Gmail will appear here.
        </td>
      </tr>
    `;
    return;
  }

  appState.history.slice().reverse().forEach(h => {
    const tr = document.createElement("tr");
    const isSent = h.status === "sent" || h.mode === "send";
    const dateStr = h.timestamp ? new Date(h.timestamp).toLocaleDateString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "Recent";

    tr.innerHTML = `
      <td class="p-4 text-[#696963] font-mono">${dateStr}</td>
      <td class="p-4 font-bold text-[#171717]">${h.brand_name || "Brand"}</td>
      <td class="p-4 text-[#696963]">${h.creator_name || "Creator"}</td>
      <td class="p-4 font-mono text-xs text-[#171717]">${h.to_email}</td>
      <td class="p-4 uppercase font-semibold text-[10px] tracking-wider text-[#A68A5B]">${h.mode || "send"}</td>
      <td class="p-4">
        <span class="editorial-badge ${isSent ? 'badge-active' : 'badge-gold'}">
          ${isSent ? 'Delivered (SMTP)' : 'Drafted (IMAP)'}
        </span>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

async function clearHistoryAction() {
  if (!confirm("Are you sure you want to clear the entire outreach audit trail?")) return;
  try {
    await fetch("/api/history", { method: "DELETE" });
    appState.history = [];
    renderHistoryTable();
    showToast("Outreach audit log cleared.");
  } catch (err) {
    showToast("Failed to clear log: " + err.message, false);
  }
}

// --- SETTINGS MODAL & GMAIL DIAGNOSTICS ---
function openSettingsModal() {
  const modal = document.getElementById("settingsModal");
  if (modal) modal.classList.remove("hidden");

  const alert = document.getElementById("gmailTestResultAlert");
  if (alert) alert.classList.add("hidden");

  const modelSelect = document.getElementById("inputOllamaModel");
  if (modelSelect && appState.ollamaModel) {
    modelSelect.value = appState.ollamaModel;
  }

  if (window.lucide) lucide.createIcons();
}

function closeSettingsModal() {
  const modal = document.getElementById("settingsModal");
  if (modal) modal.classList.add("hidden");
}

function openGmailSettingsModal() {
  openSettingsModal();
  const gmailInput = document.getElementById("inputGmailUser");
  if (gmailInput) {
    setTimeout(() => {
      gmailInput.scrollIntoView({ behavior: "smooth", block: "center" });
      gmailInput.focus();
    }, 150);
  }
}

function togglePasswordVisibility(inputId) {
  const input = document.getElementById(inputId);
  if (!input) return;
  input.type = input.type === "password" ? "text" : "password";
}

async function onModelSelectChange() {
  const modelSelect = document.getElementById("inputOllamaModel");
  const newModel = modelSelect ? modelSelect.value : "llama3.2:1b";

  try {
    const res = await fetch("/api/ollama/switch-model", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: newModel })
    });
    const data = await res.json();
    if (data.success) {
      appState.ollamaModel = newModel;
      updateAiBadge();
      const isTurbo = newModel.includes("1b");
      showToast(`Switched active model to ${newModel} (${isTurbo ? 'Turbo Speed ⚡' : 'Standard 🎯'})`);
    }
  } catch (err) {
    showToast("Failed to switch model: " + err.message, false);
  }
}

async function testGmailCredentialsLive() {
  const user = document.getElementById("inputGmailUser")?.value.trim();
  const pass = document.getElementById("inputGmailPassword")?.value.trim();
  const alert = document.getElementById("gmailTestResultAlert");
  const btn = document.getElementById("btnTestGmailText");

  if (!user || !pass) {
    if (alert) {
      alert.className = "p-3 rounded text-[11px] leading-relaxed bg-amber-50 text-amber-900 border border-amber-200 block";
      alert.innerHTML = "<strong>Missing info:</strong> Please enter both your Gmail address and 16-character App Password to test.";
    }
    return;
  }

  if (btn) btn.innerText = "Authenticating...";
  if (alert) {
    alert.className = "p-3 rounded text-[11px] leading-relaxed bg-blue-50 text-blue-900 border border-blue-200 block";
    alert.innerHTML = `Connecting to Google SMTP & IMAP as <strong>${user}</strong>...`;
  }

  try {
    const res = await fetch("/api/gmail/test-credentials", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user: user, app_password: pass })
    });
    const result = await res.json();

    if (result.connected) {
      if (alert) {
        alert.className = "p-3 rounded text-[11px] leading-relaxed bg-emerald-50 text-emerald-900 border border-emerald-300 block";
        alert.innerHTML = `<strong>✓ Connection Verified:</strong> ${result.message} Click "Save & Persist Settings" below to keep this active!`;
      }
      showToast("Gmail credentials verified successfully!");
    } else {
      if (alert) {
        alert.className = "p-3 rounded text-[11px] leading-relaxed bg-rose-50 text-rose-900 border border-rose-300 block";
        alert.innerHTML = `<strong>Authentication Failed:</strong> ${result.message}`;
      }
      showToast("Gmail authentication failed", false);
    }
  } catch (err) {
    if (alert) {
      alert.className = "p-3 rounded text-[11px] leading-relaxed bg-rose-50 text-rose-900 border border-rose-300 block";
      alert.innerHTML = `<strong>Connection Error:</strong> ${err.message}`;
    }
    showToast("Connection test error: " + err.message, false);
  } finally {
    if (btn) btn.innerText = "Test Credentials Live";
  }
}

async function saveSettings() {
  const ollamaUrl = document.getElementById("inputOllamaBaseUrl")?.value.trim() || appState.ollamaBaseUrl;
  const ollamaModel = document.getElementById("inputOllamaModel")?.value.trim() || appState.ollamaModel;
  const user = document.getElementById("inputGmailUser")?.value.trim();
  const pass = document.getElementById("inputGmailPassword")?.value.trim();
  const agency = document.getElementById("inputAgencyName")?.value.trim();
  const sender = document.getElementById("inputSenderName")?.value.trim();

  let updates = {
    OLLAMA_BASE_URL: ollamaUrl,
    OLLAMA_MODEL: ollamaModel
  };

  if (user !== undefined) updates.GMAIL_USER = user;
  if (pass !== undefined && pass.length > 0) updates.GMAIL_APP_PASSWORD = pass;
  if (agency) updates.AGENCY_NAME = agency;
  if (sender) updates.SENDER_NAME = sender;

  try {
    const res = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updates)
    });
    const result = await res.json();
    showToast("Settings saved and active!");
    closeSettingsModal();
    await loadStatus();
  } catch (err) {
    showToast("Error updating settings: " + err.message, false);
  }
}

// --- TEST EMAIL MODAL ---
function openTestEmailModal() {
  const modal = document.getElementById("testEmailModal");
  if (modal) modal.classList.remove("hidden");
  if (window.lucide) lucide.createIcons();
}

function closeTestEmailModal() {
  const modal = document.getElementById("testEmailModal");
  if (modal) modal.classList.add("hidden");
}

async function sendTestEmailAction() {
  const recipient = document.getElementById("testEmailRecipient").value.trim();
  if (!recipient) {
    showToast("Please specify a recipient email", false);
    return;
  }

  const btn = document.getElementById("sendTestBtn");
  btn.disabled = true;
  btn.innerText = "Delivering live test...";

  try {
    const creator = appState.creators.find(c => c.id === appState.selectedCreatorId) || {};
    const res = await fetch("/api/email/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        recipient: recipient,
        creator_name: creator.name || "Crevanta Talent"
      })
    });
    const result = await res.json();
    if (result.success) {
      showToast(result.message || "Test email sent successfully via Gmail!");
      closeTestEmailModal();
      await loadHistory();
    } else {
      showToast(result.message || "Failed to send test email.", false);
    }
  } catch (err) {
    showToast("Error: " + err.message, false);
  } finally {
    btn.disabled = false;
    btn.innerText = "Send Live Test Now";
  }
}

// --- CREATOR PROFILE CRUD MODAL ---
function openAddCreatorModal() {
  document.getElementById("creatorModalTitle").innerText = "Add Exclusive Creator";
  document.getElementById("creatorFormId").value = "";
  document.getElementById("creatorFormName").value = "";
  document.getElementById("creatorFormHandle").value = "";
  document.getElementById("creatorFormNiche").value = "";
  document.getElementById("creatorFormFollowers").value = "";
  document.getElementById("creatorFormEngagement").value = "";
  document.getElementById("creatorFormViews").value = "";
  document.getElementById("creatorFormBio").value = "";
  document.getElementById("creatorFormTargetBrands").value = "";
  document.getElementById("creatorFormCollabAngles").value = "";
  document.getElementById("creatorFormMediaKit").value = "";
  document.getElementById("creatorFormRates").value = "";

  const modal = document.getElementById("creatorModal");
  if (modal) modal.classList.remove("hidden");
  if (window.lucide) lucide.createIcons();
}

function editCreator(id) {
  const c = appState.creators.find(item => item.id === id);
  if (!c) return;

  document.getElementById("creatorModalTitle").innerText = `Edit ${c.name}`;
  document.getElementById("creatorFormId").value = c.id;
  document.getElementById("creatorFormName").value = c.name || "";
  document.getElementById("creatorFormHandle").value = c.handle || "";
  document.getElementById("creatorFormNiche").value = c.niche || "";
  document.getElementById("creatorFormFollowers").value = c.followers || "";
  document.getElementById("creatorFormEngagement").value = c.engagement_rate || "";
  document.getElementById("creatorFormViews").value = c.avg_views || "";
  document.getElementById("creatorFormBio").value = c.bio || "";
  document.getElementById("creatorFormTargetBrands").value = c.target_brands || "";
  document.getElementById("creatorFormCollabAngles").value = c.collab_angles || "";
  document.getElementById("creatorFormMediaKit").value = c.media_kit_url || "";
  document.getElementById("creatorFormRates").value = c.sample_rate || "";

  const modal = document.getElementById("creatorModal");
  if (modal) modal.classList.remove("hidden");
  if (window.lucide) lucide.createIcons();
}

function closeCreatorModal() {
  const modal = document.getElementById("creatorModal");
  if (modal) modal.classList.add("hidden");
}

async function submitCreatorForm() {
  const id = document.getElementById("creatorFormId").value.trim();
  const name = document.getElementById("creatorFormName").value.trim();
  const handle = document.getElementById("creatorFormHandle").value.trim();

  if (!name || !handle) {
    showToast("Name and Instagram handle are required", false);
    return;
  }

  const payload = {
    name: name,
    handle: handle,
    niche: document.getElementById("creatorFormNiche").value.trim(),
    followers: document.getElementById("creatorFormFollowers").value.trim() || "50K",
    engagement_rate: document.getElementById("creatorFormEngagement").value.trim() || "5.0%",
    avg_views: document.getElementById("creatorFormViews").value.trim() || "30K",
    bio: document.getElementById("creatorFormBio").value.trim(),
    target_brands: document.getElementById("creatorFormTargetBrands").value.trim(),
    collab_angles: document.getElementById("creatorFormCollabAngles").value.trim(),
    media_kit_url: document.getElementById("creatorFormMediaKit").value.trim(),
    sample_rate: document.getElementById("creatorFormRates").value.trim()
  };

  if (id) payload.id = id;

  try {
    const res = await fetch("/api/creators", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const saved = await res.json();
    closeCreatorModal();
    await loadCreators();
    showToast(`Creator profile for ${saved.name} saved!`);
  } catch (err) {
    showToast("Failed to save creator: " + err.message, false);
  }
}

async function deleteCreator(id) {
  if (!confirm("Are you sure you want to remove this creator profile?")) return;
  try {
    await fetch(`/api/creators/${id}`, { method: "DELETE" });
    await loadCreators();
    showToast("Creator removed from roster.");
  } catch (err) {
    showToast("Failed to delete creator: " + err.message, false);
  }
}

// --- STANDALONE BRAND RESEARCH & LEAD VERIFIER CONTROLLER ---
function copyToClipboard(text) {
  if (!text) return;
  navigator.clipboard.writeText(text).then(() => {
    showToast("Email text copied to clipboard!");
  }).catch(() => {
    showToast("Failed to copy text", false);
  });
}

async function runBrandLeadVerification() {
  const brandNameInput = document.getElementById("verifierBrandName");
  const websiteInput = document.getElementById("verifierWebsite");
  const creatorSelect = document.getElementById("verifierCreatorSelect");
  const resultArea = document.getElementById("verifierResultsArea");
  const btn = document.getElementById("runVerifierBtn");
  const btnText = document.getElementById("runVerifierBtnText");

  const brandName = brandNameInput ? brandNameInput.value.trim() : "";
  const website = websiteInput ? websiteInput.value.trim() : "";
  const creatorId = creatorSelect ? creatorSelect.value : "";

  if (!brandName || !website) {
    showToast("Please enter both Brand Name and Official Website", false);
    return;
  }

  btn.disabled = true;
  btnText.innerText = "Inspecting Official Website...";

  try {
    const indianOnly = document.getElementById("verifierIndianOnly") ? document.getElementById("verifierIndianOnly").checked : true;

    const res = await fetch("/api/verify-lead", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        brand_name: brandName,
        website: website,
        creator_id: creatorId,
        indian_only: indianOnly
      })
    });

    const data = await res.json();
    if (!data.success) {
      showToast(data.message || "Verification failed", false);
      return;
    }

    const lead = data.lead;
    const isOfficial = lead.verification === "official" && lead.recipient_email && lead.recipient_email !== "Not publicly available";

    resultArea.classList.remove("hidden");
    resultArea.innerHTML = `
      <div class="studio-module-card p-6 space-y-5">
        <!-- HEADER -->
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-[#E2DDD2]">
          <div>
            <div class="flex flex-wrap items-center gap-2.5">
              <h3 class="font-serif text-2xl font-bold text-[#141413]">${lead.brand_name}</h3>
              <a href="https://${lead.website}" target="_blank" class="text-xs text-[#B89248] hover:underline flex items-center gap-1 font-semibold">
                <span>${lead.website}</span>
                <i data-lucide="arrow-up-right" class="w-3.5 h-3.5"></i>
              </a>
              <span class="text-[10px] uppercase font-bold px-2.5 py-0.5 rounded-full bg-[#FAF5EB] text-[#8F6F30] border border-[#E8D7B8]">${lead.brand_niche || 'Target'}</span>
            </div>
            
            <div class="flex flex-wrap items-center gap-2 mt-2">
              ${isOfficial ? `
                <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-50 text-emerald-800 border border-emerald-300 shadow-sm">
                  <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                  <span>🟢 Officially Published</span>
                </span>
                <span class="text-xs text-[#66615B]">
                  Source: <a href="${(lead.email_source || '').startsWith('http') ? lead.email_source : 'https://' + lead.website}" target="_blank" class="text-[#B89248] hover:underline font-semibold">${lead.email_source}</a>
                </span>
              ` : `
                <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-amber-50 text-amber-900 border border-amber-300 shadow-sm">
                  <span class="w-2 h-2 rounded-full bg-amber-500"></span>
                  <span>🔴 Not Publicly Available</span>
                </span>
                <span class="text-xs text-[#8F6F30] italic">${lead.email_source}</span>
              `}
            </div>
          </div>

          <!-- ACTIONS -->
          <div class="flex items-center gap-2">
            <button onclick="copyToClipboard(document.getElementById('verifierEmailBody').value)" class="btn-editorial-light text-xs px-3.5 py-2 rounded-md flex items-center gap-1.5 font-semibold shadow-sm">
              <i data-lucide="copy" class="w-3.5 h-3.5 text-[#B89248]"></i>
              <span>Copy Email</span>
            </button>
            <button onclick="draftVerifiedLead('${lead.brand_name}')" class="btn-editorial-light text-xs px-3.5 py-2 rounded-md flex items-center gap-1.5 font-semibold shadow-sm">
              <i data-lucide="file-down" class="w-3.5 h-3.5 text-[#B89248]"></i>
              <span>Save Draft</span>
            </button>
            ${isOfficial ? `
              <button onclick="sendVerifiedLead('${lead.brand_name}')" class="btn-editorial-dark text-xs px-4 py-2 rounded-md flex items-center gap-1.5 font-bold shadow-md">
                <i data-lucide="send" class="w-3.5 h-3.5 text-[#B89248]"></i>
                <span>Send Live</span>
              </button>
            ` : `
              <button onclick="showToast('Cannot send: No verified official email published by brand. Crevanta never sends to unverified or guessed addresses.', false)" class="opacity-40 cursor-not-allowed bg-[#E2DDD2] text-[#66615B] text-xs px-4 py-2 rounded-md flex items-center gap-1.5 font-bold shadow-sm" title="Send locked: No verified official email published by brand.">
                <i data-lucide="lock" class="w-3.5 h-3.5"></i>
                <span>Send Locked</span>
              </button>
            `}
          </div>
        </div>

        <!-- CONTACT & AUDIT CARD -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="bg-[#FAF8F5] p-4 rounded-lg border border-[#E2DDD2]">
            <label class="block text-[11px] font-bold uppercase tracking-wider text-[#66615B] mb-1">Official Contact Address:</label>
            <div class="text-sm font-mono font-bold text-[#141413]">${lead.recipient_email}</div>
            <p class="text-[11px] text-[#66615B] mt-1">Status: <strong class="${isOfficial ? 'text-emerald-700' : 'text-amber-800'}">${isOfficial ? 'Verified Official Channel' : 'Unverified (Zero Guessing Policy)'}</strong></p>
          </div>
          <div class="bg-[#FAF8F5] p-4 rounded-lg border border-[#E2DDD2]">
            <label class="block text-[11px] font-bold uppercase tracking-wider text-[#66615B] mb-1">Official Sources Crawled:</label>
            <ul class="text-xs text-[#66615B] space-y-1 font-mono">
              ${(lead.sources_checked || []).map(s => `<li>• ${s}</li>`).join("")}
            </ul>
          </div>
        </div>

        <!-- 4-PART VIDEO CONCEPT -->
        <div class="bg-[#FAF8F5] p-5 rounded-lg border border-[#E2DDD2] space-y-3.5">
          <div class="flex items-center justify-between border-b border-[#E2DDD2] pb-2">
            <div class="flex items-center gap-2">
              <span class="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-[#141413] text-[#FAF8F5]">Video Concept</span>
              <h4 class="font-serif text-lg font-bold text-[#141413]">"${lead.part2_concept_title || 'One Wardrobe, Three Occasions'}"</h4>
            </div>
            <span class="text-[10px] text-[#B89248] font-bold uppercase tracking-wider">Crevanta 4-Part Creative Formula</span>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div class="bg-white p-3.5 rounded border border-[#E2DDD2]">
              <span class="text-[10px] font-bold uppercase tracking-wider text-[#8F6F30] block mb-1">1. Brand Insight (Differentiator)</span>
              <p class="text-xs text-[#141413] leading-relaxed">${lead.part2_brand_insight || 'Brand delivers differentiated quality in its market.'}</p>
            </div>
            <div class="bg-white p-3.5 rounded border border-[#E2DDD2]">
              <span class="text-[10px] font-bold uppercase tracking-wider text-[#8F6F30] block mb-1">2. Creative Opportunity</span>
              <p class="text-xs text-[#141413] leading-relaxed">${lead.part2_creative_opportunity || 'Integrating the product organically into authentic creator routines.'}</p>
            </div>
          </div>

          <div class="bg-white p-3.5 rounded border border-[#E2DDD2]">
            <span class="text-[10px] font-bold uppercase tracking-wider text-[#8F6F30] block mb-1">3. How It Works (Creator Action & Visual Hook)</span>
            <p class="text-xs text-[#141413] leading-relaxed">${lead.part2_how_it_works || lead.part2_video_idea}</p>
          </div>
        </div>

        <!-- FULL EMAIL BODY PREVIEW -->
        <div>
          <label class="block text-[11px] font-bold uppercase tracking-wider text-[#66615B] mb-1.5">Complete Outreach Email (3-Part Formula):</label>
          <textarea id="verifierEmailBody" rows="8" class="w-full editorial-input p-3.5 rounded-lg text-xs font-mono resize-y leading-relaxed text-[#141413]">${lead.full_email_body || lead.body}</textarea>
        </div>
      </div>
    `;

    if (window.lucide) lucide.createIcons();
    showToast(`Inspection Complete: ${isOfficial ? '🟢 Official email verified' : '🔴 No public email found (Zero guessing applied)'}`, isOfficial);
  } catch (err) {
    console.error("Verification failed:", err);
    showToast("Failed to verify brand lead", false);
  } finally {
    btn.disabled = false;
    btnText.innerText = "Verify Contact & Generate Concept";
  }
}

async function draftVerifiedLead(brandName) {
  const body = document.getElementById("verifierEmailBody").value;
  const to = document.querySelector("#verifierResultsArea .text-sm.font-mono.font-bold")?.innerText.trim() || "";
  try {
    const res = await fetch("/api/email/draft", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        to_email: to !== "Not publicly available" ? to : "",
        subject: `Partnership Concept: Crevanta × ${brandName}`,
        body: body,
        brand_name: brandName
      })
    });
    const d = await res.json();
    if (d.success) {
      showToast("Draft saved in your Gmail account!");
    } else {
      showToast(d.message || "Failed to save draft", false);
    }
  } catch (e) {
    showToast("Draft error", false);
  }
}

async function sendVerifiedLead(brandName) {
  const body = document.getElementById("verifierEmailBody").value;
  const to = document.querySelector("#verifierResultsArea .text-sm.font-mono.font-bold")?.innerText.trim() || "";
  if (!to || to === "Not publicly available") {
    showToast("Cannot send: No verified official email published by brand.", false);
    return;
  }
  try {
    const res = await fetch("/api/email/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        to_email: to,
        subject: `Partnership Concept: Crevanta × ${brandName}`,
        body: body,
        brand_name: brandName
      })
    });
    const d = await res.json();
    if (d.success) {
      showToast(`Email sent live to ${to}!`);
    } else {
      showToast(d.message || "Failed to send email", false);
    }
  } catch (e) {
    showToast("Sending error", false);
  }
}

// --- ANTI-SPAM SINGLE PITCH AUTO-SANITIZER ---
async function sanitizeSinglePitch(brandId) {
  const subjInput = document.getElementById(`email-subject-${brandId}`);
  const bodyInput = document.getElementById(`email-body-${brandId}`);
  if (!subjInput || !bodyInput) return;

  try {
    const res = await fetch("/api/anti-spam/sanitize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        subject: subjInput.value.trim(),
        body: bodyInput.value.trim()
      })
    });
    const data = await res.json();
    if (data.success) {
      subjInput.value = data.clean_subject;
      bodyInput.value = data.clean_body;

      // Update state
      const targetBrand = appState.generatedBrands.find(b => b.id === brandId);
      if (targetBrand) {
        targetBrand.subject = data.clean_subject;
        targetBrand.full_email_body = data.clean_body;
        targetBrand.body = data.clean_body;
        targetBrand.deliverability = data.deliverability;
      }

      // Update badge
      const badge = document.getElementById(`deliverability-badge-${brandId}`);
      if (badge && data.deliverability) {
        badge.className = `inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold ${data.deliverability.score >= 90 ? 'bg-emerald-50 text-emerald-800 border border-emerald-300' : 'bg-amber-50 text-amber-900 border border-amber-300'}`;
        badge.innerHTML = `<i data-lucide="shield-check" class="w-3.5 h-3.5 text-emerald-600"></i><span>${data.deliverability.score}% Primary Inbox</span>`;
        if (window.lucide) lucide.createIcons();
      }

      const count = (data.triggers_replaced || []).length;
      showToast(`Optimized for Primary Inbox! (${count} trigger items sanitized)`);
    }
  } catch (err) {
    showToast("Sanitization error: " + err.message, false);
  }
}

// --- LOAD DELIVERABILITY HEALTH STATUS ---
async function loadDeliverabilityStatus() {
  try {
    const res = await fetch("/api/deliverability/status");
    if (!res.ok) return;
    const data = await res.json();
    const quotaDisplay = document.getElementById("dailyQuotaDisplay");
    if (quotaDisplay) {
      quotaDisplay.innerText = `${data.today_sent_count} / ${data.safe_daily_limit} sent today (${data.reputation_status})`;
    }
  } catch (e) {
    // Non-blocking
  }
}

// =========================================================================
// SELF-HOSTED EMAIL VERIFICATION CHECKER & INDIAN BRAND PIPELINE (UI)
// =========================================================================
let cachedEvHistory = [];

async function refreshVerifierStatsAndRecords() {
  await Promise.all([
    loadEmailVerificationStats(),
    loadEmailVerificationHistory()
  ]);
}

async function loadEmailVerificationStats() {
  try {
    const res = await fetch("/api/email-verifier/stats");
    if (!res.ok) return;
    const stats = await res.json();
    const setTxt = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.innerText = val;
    };
    setTxt("statTotal", stats.total || 0);
    setTxt("statValid", stats.valid || 0);
    setTxt("statCatchAll", stats.catch_all || 0);
    setTxt("statDisposable", stats.disposable || 0);
    setTxt("statInvalid", stats.invalid || 0);
    setTxt("statIndian", stats.indian_entities || 0);
  } catch (err) {
    console.error("Failed to load verification stats:", err);
  }
}

async function runSingleEmailVerification() {
  const input = document.getElementById("evSingleInput");
  const indianFilter = document.getElementById("evSingleIndianFilter");
  const force = document.getElementById("evSingleForce");
  const btn = document.getElementById("evSingleBtn");
  const card = document.getElementById("evSingleResultCard");

  const val = input ? input.value.trim() : "";
  if (!val) {
    showToast("Please enter an email or domain to verify", false);
    return;
  }

  btn.disabled = true;
  btn.innerHTML = `<span class="animate-spin mr-1">⏳</span> Checking...`;

  try {
    const res = await fetch("/api/email-verifier/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email_or_domain: val,
        check_indian_only: indianFilter ? indianFilter.checked : true,
        force_recheck: force ? force.checked : false
      })
    });

    const data = await res.json();
    card.classList.remove("hidden");

    let badgeClass = "bg-rose-50 text-rose-800 border-rose-300";
    let badgeIcon = "x-circle";
    let badgeText = (data.status || "invalid").toUpperCase();

    if (data.status === "valid") {
      badgeClass = "bg-emerald-50 text-emerald-800 border-emerald-300";
      badgeIcon = "check-circle";
    } else if (data.status === "catch-all") {
      badgeClass = "bg-amber-50 text-amber-800 border-amber-300";
      badgeIcon = "alert-triangle";
      badgeText = "CATCH-ALL (UNVERIFIABLE)";
    } else if (data.status === "disposable") {
      badgeClass = "bg-purple-50 text-purple-800 border-purple-300";
      badgeIcon = "shield-alert";
      badgeText = "DISPOSABLE BLOCKED";
    } else if (data.status === "timeout") {
      badgeClass = "bg-slate-50 text-slate-800 border-slate-300";
      badgeIcon = "clock";
      badgeText = "TIMEOUT";
    }

    card.className = `p-4 rounded-lg border text-xs space-y-2.5 ${data.approved ? 'border-emerald-200 bg-emerald-50/40' : 'border-rose-200 bg-rose-50/30'}`;
    card.innerHTML = `
      <div class="flex items-center justify-between">
        <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold border ${badgeClass}">
          <i data-lucide="${badgeIcon}" class="w-3.5 h-3.5"></i>
          <span>${badgeText}</span>
        </span>
        <div class="flex items-center gap-2">
          ${data.is_indian ? `<span class="px-2 py-0.5 rounded bg-orange-100 text-orange-800 border border-orange-200 font-bold text-[10px]">🇮🇳 Indian Entity</span>` : `<span class="px-2 py-0.5 rounded bg-gray-100 text-gray-700 text-[10px]">Non-Indian</span>`}
          ${data.cached ? `<span class="text-[10px] text-[#66615B] italic">From Cache</span>` : `<span class="text-[10px] text-[#66615B] italic">Live Network</span>`}
        </div>
      </div>

      <div class="space-y-1">
        <div class="text-sm font-bold text-[#141413] font-mono">${data.email || data.domain}</div>
        <div class="text-xs text-[#66615B]">${data.reason || 'Verification completed'}</div>
      </div>

      <div class="pt-2 border-t border-[#E2DDD2] grid grid-cols-2 gap-2 text-[11px] text-[#66615B]">
        <div><span class="font-bold">MX Host:</span> ${data.mx_host || 'N/A'}</div>
        <div><span class="font-bold">SMTP Code:</span> ${data.smtp_code ? data.smtp_code : 'N/A'}</div>
      </div>
    `;

    if (window.lucide) lucide.createIcons();
    await refreshVerifierStatsAndRecords();
  } catch (err) {
    showToast("Verification error: " + err.message, false);
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<span>Verify Live</span>`;
  }
}

function handleCsvFileSelected(event) {
  const file = event.target.files[0];
  if (!file) return;
  const nameSpan = document.getElementById("evSelectedCsvName");
  if (nameSpan) nameSpan.innerText = file.name;

  const reader = new FileReader();
  reader.onload = (e) => {
    const text = e.target.result;
    const txtArea = document.getElementById("evBatchInput");
    if (txtArea) txtArea.value = text;
  };
  reader.readAsText(file);
}

async function runBatchEmailVerification() {
  const txtArea = document.getElementById("evBatchInput");
  const raw = txtArea ? txtArea.value.trim() : "";
  const resultArea = document.getElementById("evBatchResultArea");
  const btn = document.getElementById("evBatchBtn");

  if (!raw) {
    showToast("Please paste email addresses or upload a CSV first", false);
    return;
  }

  btn.disabled = true;
  btn.innerHTML = `<span class="animate-spin mr-1">⏳</span> Processing...`;

  try {
    let res;
    if (raw.includes(",") || raw.includes("\n")) {
      res = await fetch("/api/email-verifier/upload-csv", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          csv_content: raw,
          check_indian_only: true
        })
      });
    } else {
      res = await fetch("/api/email-verifier/batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          items: raw.split("\n").map(s => s.trim()).filter(Boolean),
          check_indian_only: true
        })
      });
    }

    const data = await res.json();
    resultArea.classList.remove("hidden");

    const validCount = (data || []).filter(r => r.status === "valid").length;
    const catchAllCount = (data || []).filter(r => r.status === "catch-all").length;
    const rejectedCount = (data || []).length - validCount - catchAllCount;

    resultArea.innerHTML = `
      <div class="flex items-center justify-between pb-2 border-b border-[#E2DDD2]">
        <span class="font-bold text-[#141413]">Batch Complete: ${data.length} checked</span>
        <div class="flex items-center gap-2 text-[11px]">
          <span class="text-emerald-700 font-bold">${validCount} Valid</span>
          <span class="text-amber-700 font-bold">${catchAllCount} Catch-All</span>
          <span class="text-rose-700 font-bold">${rejectedCount} Rejected</span>
        </div>
      </div>
      <div class="max-h-40 overflow-y-auto space-y-1 divide-y divide-[#E2DDD2]">
        ${data.map(item => `
          <div class="pt-1.5 flex items-center justify-between">
            <span class="font-mono text-[11px] text-[#141413]">${item.email || item.domain}</span>
            <span class="text-[10px] uppercase font-bold px-2 py-0.5 rounded ${
              item.status === 'valid' ? 'bg-emerald-100 text-emerald-800' :
              item.status === 'catch-all' ? 'bg-amber-100 text-amber-800' :
              item.status === 'disposable' ? 'bg-purple-100 text-purple-800' : 'bg-rose-100 text-rose-800'
            }">${item.status}</span>
          </div>
        `).join('')}
      </div>
    `;

    showToast(`Batch verification finished: ${validCount} valid inboxes approved`);
    await refreshVerifierStatsAndRecords();
  } catch (err) {
    showToast("Batch processing error: " + err.message, false);
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<i data-lucide="play" class="w-3.5 h-3.5 text-[#B89248]"></i><span>Process Batch</span>`;
    if (window.lucide) lucide.createIcons();
  }
}

async function loadEmailVerificationHistory() {
  const filterSelect = document.getElementById("evTableFilter");
  const statusFilter = filterSelect ? filterSelect.value : "";
  const tbody = document.getElementById("evHistoryTbody");

  try {
    let url = "/api/email-verifier/records?limit=50";
    if (statusFilter) url += `&status=${statusFilter}`;
    const res = await fetch(url);
    if (!res.ok) return;
    const records = await res.json();
    cachedEvHistory = records;

    if (!tbody) return;
    if (!records || records.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" class="py-6 text-center text-xs text-[#66615B] italic">No email verification records found in SQLite database yet.</td></tr>`;
      return;
    }

    tbody.innerHTML = records.map(r => {
      let badgeStyle = "bg-rose-50 text-rose-800 border-rose-200";
      if (r.status === "valid") badgeStyle = "bg-emerald-50 text-emerald-800 border-emerald-200";
      else if (r.status === "catch-all") badgeStyle = "bg-amber-50 text-amber-800 border-amber-200";
      else if (r.status === "disposable") badgeStyle = "bg-purple-50 text-purple-800 border-purple-200";
      else if (r.status === "timeout") badgeStyle = "bg-slate-50 text-slate-800 border-slate-200";

      const timeFormatted = (r.updated_at || r.created_at || "").replace("T", " ").split(".")[0];

      return `
        <tr class="border-b border-[#E2DDD2] hover:bg-[#FAF8F5] transition">
          <td class="py-2.5 px-3 font-mono font-medium text-[#141413]">${r.email || r.domain}</td>
          <td class="py-2.5 px-3">
            <span class="inline-block uppercase text-[10px] font-bold px-2 py-0.5 rounded border ${badgeStyle}">
              ${r.status}
            </span>
          </td>
          <td class="py-2.5 px-3">
            ${r.is_indian ? `<span class="text-orange-700 font-bold">🇮🇳 Indian Brand</span>` : `<span class="text-[#888]">Non-Indian</span>`}
          </td>
          <td class="py-2.5 px-3 font-mono text-[11px] text-[#66615B]">${r.mx_host || '—'}</td>
          <td class="py-2.5 px-3 font-mono text-[11px]">${r.smtp_code ? r.smtp_code : '—'}</td>
          <td class="py-2.5 px-3 text-[11px] text-[#66615B] max-w-[220px] truncate" title="${r.reason || ''}">${r.reason || '—'}</td>
          <td class="py-2.5 px-3 text-[10px] text-[#888]">${timeFormatted}</td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    console.error("Failed to load verification records:", err);
  }
}

function downloadVerificationHistoryCsv() {
  if (!cachedEvHistory || cachedEvHistory.length === 0) {
    showToast("No verification records to export", false);
    return;
  }
  const headers = ["email", "domain", "status", "is_indian", "mx_host", "smtp_code", "reason", "updated_at"];
  let csvContent = headers.join(",") + "\n";

  cachedEvHistory.forEach(r => {
    const row = [
      `"${r.email || ''}"`,
      `"${r.domain || ''}"`,
      `"${r.status || ''}"`,
      r.is_indian ? "1" : "0",
      `"${r.mx_host || ''}"`,
      r.smtp_code || "0",
      `"${(r.reason || '').replace(/"/g, '""')}"`,
      `"${r.updated_at || ''}"`
    ];
    csvContent += row.join(",") + "\n";
  });

  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.setAttribute("href", url);
  link.setAttribute("download", `crevanta_email_verifications_${Date.now()}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  showToast("Exported verification records CSV");
}


