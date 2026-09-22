const qs = (s) => document.querySelector(s);
const selectedTags = new Set();
let refreshing = false;

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: {"Content-Type": "application/json", ...(options.headers || {})},
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
  return payload;
}

async function refresh({checkArtist = false} = {}) {
  if (refreshing) return;
  refreshing = true;
  try {
    BlackInkUI.render(await api("/api/state"));
    if (checkArtist) await checkComfy();
  } catch (error) {
    qs("#statusLine").innerHTML = `<span class="error">${BlackInkUI.esc(error.message)}</span>`;
  } finally {
    refreshing = false;
  }
}

async function decide(decision) {
  try {
    const data = await api("/api/decision", {
      method: "POST",
      body: JSON.stringify({
        decision,
        notes: qs("#notes").value,
        quick_tags: [...selectedTags],
      }),
    });
    qs("#notes").value = "";
    selectedTags.clear();
    document.querySelectorAll("[data-tag]").forEach((button) => {
      button.classList.remove("selected");
    });
    BlackInkUI.render(data);
    await checkComfy();
  } catch (error) {
    qs("#statusLine").innerHTML = `<span class="error">${BlackInkUI.esc(error.message)}</span>`;
  }
}

async function generateNow() {
  try {
    BlackInkUI.render(await api("/api/generate", {method: "POST", body: "{}"}));
    await checkComfy();
  } catch (error) {
    qs("#statusLine").innerHTML = `<span class="error">${BlackInkUI.esc(error.message)}</span>`;
  }
}

async function checkComfy() {
  const el = qs("#comfyStatus");
  if (!el) return;
  try {
    const data = await api("/api/comfy-health");
    if (!data.connected) throw new Error("offline");
    const gpu = data.devices?.[0]?.name || "GPU detected";
    el.className = "comfy-status comfy-ok";
    el.textContent = "Local artist connected · " + gpu;
  } catch {
    el.className = "comfy-status comfy-off";
    el.textContent = "Local artist offline";
  }
}

document.querySelectorAll("[data-tag]").forEach((button) => {
  button.addEventListener("click", () => {
    const tag = button.dataset.tag;
    if (selectedTags.has(tag)) {
      selectedTags.delete(tag);
      button.classList.remove("selected");
    } else {
      selectedTags.add(tag);
      button.classList.add("selected");
    }
  });
});

qs("#approve").addEventListener("click", () => decide("approve"));
qs("#modify").addEventListener("click", () => decide("modify"));
qs("#regenerate").addEventListener("click", () => decide("regenerate"));
qs("#generate").addEventListener("click", generateNow);

refresh({checkArtist: true});
setInterval(refresh, 2500);
setInterval(checkComfy, 10000);
