const qs = (s) => document.querySelector(s);

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

function list(items) {
  return `<ul>${(items || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`;
}

function candidateUrl(path, version = "") {
  const relative = String(path || "").replace(/^\/+/, "");
  return `/${relative}?v=${encodeURIComponent(version)}`;
}

function renderImage(page, state, generating) {
  const candidate = state.current_candidate;
  if (!candidate?.image_path) {
    qs("#artFrame").innerHTML = `
      <div class="placeholder"><div>
        <strong>${esc(page.page_id)} · ${esc(page.monster_name)}</strong><br><br>
        ${generating ? "Generating locally now..." : "No generated candidate yet."}
      </div></div>`;
    return;
  }

  const url = candidateUrl(candidate.image_path, candidate.created_at || "");
  qs("#artFrame").innerHTML =
    `<img src="${esc(url)}" alt="Current ${esc(page.monster_name)} candidate">`;
  qs("#artFrame img")?.addEventListener("error", () => {
    qs("#artFrame").innerHTML = `
      <div class="placeholder candidate-error"><div>
        <strong>Preview could not load.</strong><br><br>
        <a href="${esc(url)}" target="_blank" rel="noopener">Open generated image directly</a>.
      </div></div>`;
  }, {once: true});
}

function renderEnvironment(page) {
  const env = page.environment || {};
  qs("#environmentPanel").innerHTML = `
    <h3>${esc(env.identity || page.habitat)}</h3>
    <p><strong>Visual anchors</strong></p>${list(env.anchors)}
    <p><strong>Monster ↔ environment interaction</strong></p>
    <p>${esc(env.interaction || "")}</p>
    <p><strong>Coloring value</strong></p>${list(env.coloring_value)}
    <p><strong>Avoid</strong></p>${list(env.must_avoid)}
  `;
}

function renderMonster(spec) {
  const visual = spec?.visual_identity || {};
  const ref = spec?.reference || {};
  qs("#referencePanel").innerHTML = spec ? `
    <div class="reference-head"><div>
      <p class="eyebrow">Canonical Monster Identity</p><h3>${esc(spec.monster_name)}</h3>
    </div><span class="identity-badge">${esc(spec.family || "monster")}</span></div>
    ${ref.resolved_image
      ? `<img class="reference-image" src="${esc(ref.resolved_image)}" alt="Identity reference">`
      : `<div class="reference-placeholder"><strong>Identity brief active</strong>
           <span>Anatomy rules drive generation.</span></div>`}
    <p class="identity-core">${esc(visual.core_identity || "")}</p>
    <dl class="identity-facts">
      <dt>Silhouette</dt><dd>${esc(visual.silhouette || "")}</dd>
      <dt>Head</dt><dd>${esc(visual.head_features || "")}</dd>
      <dt>Body</dt><dd>${esc(visual.body_shape || "")}</dd>
    </dl>
    <h4>Monster Accuracy Check</h4>${list(spec.accuracy_checks)}
  ` : `<div class="reference-placeholder"><strong>Canonical spec required</strong></div>`;
}

function renderBrief(page) {
  qs("#brief").innerHTML = `
    <h3>Archetype</h3><p>${esc((page.archetype || "default_scene").replaceAll("_", " "))}</p>
    <h3>Moment</h3><p>${esc(page.moment)}</p>
    <h3>Identity</h3>${list(page.identity_rules)}
    <h3>Must Include</h3>${list(page.must_include)}
    <h3>Must Avoid</h3>${list(page.must_avoid)}
  `;
}

function renderStatus(page, state, worker) {
  const c = state.current_candidate;
  const generating = state.status === "generating" || worker.running;
  if (generating) return `<strong>Generating ${esc(page.monster_name)} locally...</strong>`;
  if (state.generation_error?.message) {
    return `<span class="error"><strong>Generation stopped:</strong> ${esc(state.generation_error.message)}</span>`;
  }
  if (!c) return "<strong>Ready to generate.</strong>";
  const mode = c.generation_mode ? ` · Mode: <strong>${esc(c.generation_mode.replaceAll("_", " "))}</strong>` : "";
  const retry = c.technical_retry ? ` · Auto-retries: <strong>${c.technical_retry}</strong>` : "";
  return `Attempt <strong>${c.attempt}</strong>${mode}${retry} · QA: <strong>${esc(c.qa_status)}</strong>`;
}

function render(data) {
  const p = data.current_page, s = data.current_state, c = s.current_candidate;
  const worker = data.generation_worker || {};
  const generating = s.status === "generating" || worker.running;
  const canGenerate = ["queued","modify_requested","regenerate_requested","generation_failed"].includes(s.status)
    && !worker.running && Boolean(p.monster_spec_id);

  qs("#bookId").textContent = data.tome.tome_id || "Active Book";
  qs("#bookTitle").textContent = data.tome.title || "Untitled";
  qs("#progress").innerHTML = `<div><strong>${data.progress.approved}/${data.progress.total}</strong></div>
    <div>pages approved</div><div id="comfyStatus" class="comfy-status">Checking local artist...</div>`;
  qs("#pageHeader").innerHTML = `<div><p class="eyebrow">${esc(p.page_id)} · Page ${p.order} of ${data.progress.total}</p>
    <h2>${esc(p.monster_name)}</h2><p class="tagline">${esc(p.habitat)}</p></div>
    <span class="badge">${esc(s.status.replaceAll("_", " "))}</span>`;

  renderImage(p, s, generating);
  renderEnvironment(p);
  renderMonster(data.current_monster_spec);
  renderBrief(p);
  qs("#queue").innerHTML = data.ordered_pages.map((x) => `
    <div class="queue-row ${x.page_id === data.current_page_id ? "current" : ""} ${x.status === "locked" ? "locked" : ""}">
      <span>${esc(x.page_id)}</span><span>${esc(x.monster_name)}</span><span class="state">${esc(x.status)}</span>
    </div>`).join("");

  qs("#approve").disabled = !(c && s.status === "awaiting_human") || generating;
  qs("#modify").disabled = !c || generating;
  qs("#regenerate").disabled = !c || generating;
  qs("#generate").disabled = !canGenerate;
  qs("#statusLine").innerHTML = renderStatus(p, s, worker);
}

window.BlackInkUI = {render, esc};
