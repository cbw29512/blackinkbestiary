let goldenSelectedPageId = null;
let goldenRefreshing = false;

async function goldenApi(path, options = {}) {
  try {
    const response = await fetch(path, {
      headers: {"Content-Type": "application/json", ...(options.headers || {})},
      ...options,
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    return payload;
  } catch (error) {
    throw new Error(`Golden Five request failed: ${error.message}`);
  }
}

function goldenEsc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

function goldenImageUrl(path, version = "") {
  const relative = String(path || "").replace(/^\/+/, "");
  return `/${relative}?v=${encodeURIComponent(version)}`;
}

function goldenSelected(data) {
  const pages = data.pages || [];
  const existing = pages.find((page) => page.page_id === goldenSelectedPageId);
  if (existing) return existing;
  const next = pages.find((page) => page.status !== "locked") || pages[0] || null;
  goldenSelectedPageId = next?.page_id || null;
  return next;
}

function goldenDimensions(page, required) {
  const stored = page?.review_dimensions || {};
  return required.map((name) => {
    const checked = stored[name] === false ? "checked" : "";
    return `<label class="golden-dimension">
      <input type="checkbox" value="${goldenEsc(name)}" ${checked}>
      ${goldenEsc(name.replaceAll("_", " "))}
    </label>`;
  }).join("");
}

function renderGolden(data) {
  const root = document.querySelector("#goldenFive");
  if (!root) return;
  const page = goldenSelected(data);
  const report = data.report || {};
  const worker = data.worker || {};
  if (!page) {
    root.innerHTML = '<p class="error">Golden Five configuration has no pages.</p>';
    return;
  }

  const candidate = page.current_candidate;
  const waiting = page.status === "awaiting_human";
  const generatable = ["pending", "regenerate_requested"].includes(page.status) && !worker.running;
  const locked = page.status === "locked";
  const imageUrl = candidate?.image_path
    ? goldenImageUrl(candidate.image_path, candidate.created_at || candidate.candidate_id || "")
    : "";

  root.innerHTML = `
    <div class="golden-progress">
      <strong>${report.approved || 0}/${report.required || 5}</strong>
      <span>${report.production_calibrated ? "calibrated · mass generation unlocked" : "reference pages approved"}</span>
    </div>
    <div class="golden-tabs">
      ${(data.pages || []).map((item) => `
        <button type="button" data-golden-page="${goldenEsc(item.page_id)}"
          class="${item.page_id === page.page_id ? "selected" : ""} ${item.status === "locked" ? "passed" : ""}">
          ${goldenEsc(item.page_id)}
        </button>
      `).join("")}
    </div>
    <div class="golden-brief">
      <strong>${goldenEsc(page.page_id)} · ${goldenEsc(page.monster_name)}</strong>
      <span>${goldenEsc(page.status.replaceAll("_", " "))}</span>
      <p>${goldenEsc(page.calibration_role)}</p>
      <p><strong>Special:</strong> ${goldenEsc(page.special_rule)}</p>
    </div>
    ${imageUrl ? `
      <a href="${goldenEsc(imageUrl)}" target="_blank" rel="noopener" class="golden-preview-link">
        <img src="${goldenEsc(imageUrl)}" class="golden-preview" alt="Golden Five ${goldenEsc(page.monster_name)} candidate">
        <span>Open full-size candidate</span>
      </a>
    ` : '<div class="reference-placeholder"><strong>No calibration candidate yet</strong><span>Generate this page without advancing Tome I.</span></div>'}
    ${waiting ? `
      <p class="golden-help">For rejection, check every dimension that failed:</p>
      <div class="golden-dimensions">${goldenDimensions(page, data.required_review_dimensions || [])}</div>
      <textarea id="goldenNotes" rows="2" placeholder="Optional calibration notes"></textarea>
    ` : ""}
    <div class="golden-actions">
      <button id="goldenGenerate" type="button" class="generate" ${generatable ? "" : "disabled"}>
        ${page.attempt ? "Regenerate calibration" : "Generate calibration"}
      </button>
      <button id="goldenApprove" type="button" class="approve" ${waiting ? "" : "disabled"}>Approve Golden</button>
      <button id="goldenReject" type="button" class="regenerate" ${waiting ? "" : "disabled"}>Reject & Regenerate</button>
    </div>
    ${worker.running ? `<p class="golden-worker">Generating ${goldenEsc(worker.page_id)} locally...</p>` : ""}
    ${locked ? '<p class="golden-pass">This reference page passed all six quality dimensions.</p>' : ""}
    <p id="goldenError" class="error"></p>
  `;

  root.querySelectorAll("[data-golden-page]").forEach((button) => {
    button.addEventListener("click", () => {
      goldenSelectedPageId = button.dataset.goldenPage;
      renderGolden(data);
    });
  });
  root.querySelector("#goldenGenerate")?.addEventListener("click", () => generateGolden(page.page_id));
  root.querySelector("#goldenApprove")?.addEventListener("click", () => reviewGolden(page.page_id, "approve"));
  root.querySelector("#goldenReject")?.addEventListener("click", () => reviewGolden(page.page_id, "reject"));
}

async function refreshGolden() {
  if (goldenRefreshing) return;
  goldenRefreshing = true;
  try {
    renderGolden(await goldenApi("/api/golden-five"));
  } catch (error) {
    const root = document.querySelector("#goldenFive");
    if (root) root.innerHTML = `<p class="error">${goldenEsc(error.message)}</p>`;
  } finally {
    goldenRefreshing = false;
  }
}

async function generateGolden(pageId) {
  try {
    renderGolden(await goldenApi("/api/golden-five/generate", {
      method: "POST",
      body: JSON.stringify({page_id: pageId}),
    }));
  } catch (error) {
    const el = document.querySelector("#goldenError");
    if (el) el.textContent = error.message;
  }
}

async function reviewGolden(pageId, decision) {
  try {
    const failed = [...document.querySelectorAll(".golden-dimension input:checked")].map((el) => el.value);
    const notes = document.querySelector("#goldenNotes")?.value || "";
    if (decision === "reject" && failed.length === 0) {
      throw new Error("Check at least one failed quality dimension before rejecting.");
    }
    let data = await goldenApi("/api/golden-five/review", {
      method: "POST",
      body: JSON.stringify({page_id: pageId, decision, failed_dimensions: failed, notes}),
    });
    if (decision === "reject") {
      data = await goldenApi("/api/golden-five/generate", {
        method: "POST",
        body: JSON.stringify({page_id: pageId}),
      });
    }
    renderGolden(data);
  } catch (error) {
    const el = document.querySelector("#goldenError");
    if (el) el.textContent = error.message;
  }
}

refreshGolden();
setInterval(refreshGolden, 2500);
