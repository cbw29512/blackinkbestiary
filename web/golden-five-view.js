function goldenEsc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

function goldenImageUrl(path, version = "") {
  const relative = String(path || "").replace(/^\/+/, "");
  return `/${relative}?v=${encodeURIComponent(version)}`;
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

function renderGoldenView(data, page) {
  const root = document.querySelector("#goldenFive");
  if (!root) return;
  if (!page) {
    root.innerHTML = '<p class="error">Golden Five configuration has no pages.</p>';
    return;
  }
  const report = data.report || {};
  const worker = data.worker || {};
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
    ${worker.reason === "local_generation_preflight_failed" ? '<p class="error">Local artist is not generation-ready. See the readiness status at the top of the Studio.</p>' : ""}
    ${page.generation_error?.message ? `<p class="error"><strong>Generation failed:</strong> ${goldenEsc(page.generation_error.message)}</p>` : ""}
    ${locked ? '<p class="golden-pass">This reference page passed all six quality dimensions.</p>' : ""}
    <p id="goldenError" class="error"></p>
  `;
}
