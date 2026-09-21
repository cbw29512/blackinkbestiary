const qs = (selector) => document.querySelector(selector);
const selectedTags = new Set();

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: {"Content-Type": "application/json", ...(options.headers || {})},
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
  return payload;
}

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[char]));
}

function list(items) {
  return `<ul>${(items || []).map((item) => `<li>${esc(item)}</li>`).join("")}</ul>`;
}

function render(data) {
  const page = data.current_page;
  const state = data.current_state;
  const candidate = state.current_candidate;

  qs("#progress").innerHTML =
    `<div><strong>${data.progress.approved}/${data.progress.total}</strong></div><div>pages approved</div>`;

  qs("#pageHeader").innerHTML = `
    <div>
      <p class="eyebrow">${esc(page.page_id)} · Page ${page.order} of ${data.progress.total}</p>
      <h2>${esc(page.monster_name)}</h2>
      <p class="tagline">${esc(page.habitat)}</p>
    </div>
    <span class="badge">${esc(state.status.replaceAll("_", " "))}</span>
  `;

  if (candidate?.image_path) {
    qs("#artFrame").innerHTML =
      `<img src="${esc(candidate.image_path)}?v=${encodeURIComponent(candidate.created_at || "")}" alt="Current ${esc(page.monster_name)} candidate">`;
  } else if (page.reference_image) {
    qs("#artFrame").innerHTML = `
      <div class="reference-wrap">
        <img src="${esc(page.reference_image)}" alt="${esc(page.monster_name)} reference art">
        <span class="reference-label">REFERENCE — waiting for local AI refinement</span>
      </div>
    `;
  } else {
    qs("#artFrame").innerHTML = `
      <div class="placeholder"><div>
        <strong>${esc(page.page_id)} · ${esc(page.monster_name)}</strong><br><br>
        No generated candidate yet.<br>The page stays here until the local art worker produces one.
      </div></div>
    `;
  }

  qs("#brief").innerHTML = `
    <h3>Moment</h3><p>${esc(page.moment)}</p>
    <h3>Identity</h3>${list(page.identity_rules)}
    <h3>Must Include</h3>${list(page.must_include)}
    <h3>Must Avoid</h3>${list(page.must_avoid)}
    ${page.modify ? `
      <h3>Current Modify Direction</h3>
      <p><strong>Preserve:</strong></p>${list(page.modify.preserve)}
      <p><strong>Change:</strong></p>${list(page.modify.change)}
      <p><strong>Avoid:</strong></p>${list(page.modify.avoid)}
    ` : ""}
  `;

  qs("#queue").innerHTML = data.ordered_pages.map((entry) => `
    <div class="queue-row ${entry.page_id === data.current_page_id ? "current" : ""} ${entry.status === "locked" ? "locked" : ""}">
      <span>${esc(entry.page_id)}</span>
      <span>${esc(entry.monster_name)}</span>
      <span class="state">${esc(entry.status)}</span>
    </div>
  `).join("");

  const reviewReady = Boolean(candidate && state.status === "awaiting_human");
  qs("#approve").disabled = !reviewReady;
  qs("#modify").disabled = !reviewReady;
  qs("#regenerate").disabled = !reviewReady;

  if (state.worker_message && state.status !== "awaiting_human") {
    qs("#statusLine").innerHTML = `<strong>${esc(state.worker_message)}</strong>`;
  } else if (candidate) {
    const score = candidate.qa_score == null ? "" : ` · QA score: <strong>${esc(candidate.qa_score)}</strong>`;
    qs("#statusLine").innerHTML =
      `Attempt <strong>${candidate.attempt}</strong> · QA: <strong>${esc(candidate.qa_status)}</strong>${score} · Preflight: <strong>${esc(candidate.supervisor_status)}</strong>`;
  } else {
    qs("#statusLine").innerHTML =
      "<strong>No active candidate.</strong> Waiting for the local art worker.";
  }
}

async function refresh() {
  try {
    render(await api("/api/state"));
  } catch (error) {
    qs("#statusLine").innerHTML = `<span class="error">${esc(error.message)}</span>`;
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
    document.querySelectorAll("[data-tag]").forEach((button) => button.classList.remove("selected"));
    render(data);
  } catch (error) {
    qs("#statusLine").innerHTML = `<span class="error">${esc(error.message)}</span>`;
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

refresh();
setInterval(refresh, 3000);
