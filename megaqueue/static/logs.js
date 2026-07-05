const MODULE_COLOURS = {
  sync: { text: "text-[#5BA4E6]", bg: "bg-[#1E3A5F]", border: "border-[#2A4A6F]" },
  worker: { text: "text-[#6E7790]", bg: "bg-[#252A3C]", border: "border-[#353A4C]" },
  metadata: { text: "text-[#9B7ED8]", bg: "bg-[#2D2444]", border: "border-[#3D3454]" },
  organiser: { text: "text-[#5DB87A]", bg: "bg-[#1A3328]", border: "border-[#2A4338]" },
  lifecycle: { text: "text-[#D4943C]", bg: "bg-[#3D2E1A]", border: "border-[#4D3E2A]" },
  notifications: { text: "text-[#5BB8B0]", bg: "bg-[#1A3330]", border: "border-[#2A4340]" },
  app: { text: "text-[#C8CDD8]", bg: "bg-[#252A3C]", border: "border-[#353A4C]" },
  migrations: { text: "text-[#C9B458]", bg: "bg-[#3A3520]", border: "border-[#4A4530]" },
};

const LEVEL_COLOURS = {
  ERROR: "text-[#D45D5D]",
  WARNING: "text-[#C9B458]",
  INFO: "",
};

const DEFAULT_COLOUR = { text: "text-[#6E7790]", bg: "bg-[#252A3C]", border: "border-[#353A4C]" };

const container = document.getElementById("log-container");
const logList = document.getElementById("log-list");
const filtersEl = document.getElementById("filters");

let autoScroll = true;
let activeModules = new Set();
let knownModules = new Set();

function moduleColour(mod) {
  return MODULE_COLOURS[mod] || DEFAULT_COLOUR;
}

function isVisible(mod) {
  return activeModules.size === 0 || activeModules.has(mod);
}

function formatTime(iso) {
  const d = new Date(iso + "Z");
  return d.toLocaleTimeString("en-GB", { hour12: false });
}

function createLogRow(entry) {
  const row = document.createElement("div");
  row.className = "flex gap-3 px-3 py-0.5 hover:bg-[#252A3C]/50 min-w-0";
  row.dataset.module = entry.module;
  if (!isVisible(entry.module)) row.style.display = "none";

  const col = moduleColour(entry.module);
  const msgClass = entry.level === "ERROR" ? "text-[#D45D5D]" : entry.level === "WARNING" ? "text-[#C9B458]" : "text-[#C8CDD8]";

  row.innerHTML =
    `<span class="text-[#6E7790] shrink-0">${formatTime(entry.timestamp)}</span>` +
    `<span class="${col.text} shrink-0 w-24 text-right">${entry.module}</span>` +
    `<span class="${msgClass} break-all min-w-0">${escapeHtml(entry.message)}</span>`;

  return row;
}

function escapeHtml(s) {
  const el = document.createElement("span");
  el.textContent = s;
  return el.innerHTML;
}

function appendEntry(entry) {
  registerModule(entry.module);
  const row = createLogRow(entry);
  logList.appendChild(row);
  if (autoScroll) container.scrollTop = container.scrollHeight;
}

function registerModule(mod) {
  if (knownModules.has(mod)) return;
  knownModules.add(mod);
  renderFilters();
}

function renderFilters() {
  filtersEl.innerHTML = "";
  for (const mod of [...knownModules].sort()) {
    const col = moduleColour(mod);
    const active = activeModules.has(mod);
    const chip = document.createElement("button");
    chip.className = `px-2 py-0.5 rounded text-xs border ${active ? col.bg + " " + col.border + " " + col.text : "bg-[#1A1F30] border-[#252A3C] text-[#6E7790]"}`;
    chip.textContent = mod;
    chip.onclick = () => toggleModule(mod);
    filtersEl.appendChild(chip);
  }
}

function toggleModule(mod) {
  if (activeModules.has(mod)) {
    activeModules.delete(mod);
  } else {
    activeModules.add(mod);
  }
  applyFilters();
  renderFilters();
}

function applyFilters() {
  for (const row of logList.children) {
    row.style.display = isVisible(row.dataset.module) ? "" : "none";
  }
}

container.addEventListener("scroll", () => {
  const threshold = 40;
  autoScroll = container.scrollTop + container.clientHeight >= container.scrollHeight - threshold;
});

fetch("/api/logs")
  .then((r) => r.json())
  .then((entries) => {
    autoScroll = false;
    for (const e of entries) appendEntry(e);
    autoScroll = true;
    requestAnimationFrame(() => {
      container.scrollTop = container.scrollHeight;
    });
  });

const evtSource = new EventSource("/api/logs/stream");
evtSource.onmessage = (e) => {
  const entry = JSON.parse(e.data);
  appendEntry(entry);
};
