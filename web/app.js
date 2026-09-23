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

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

function list(items) {
  return `<ul>${(items || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`;
}

function candidateImageUrl(imagePath, version = "") {
  const relative = String(imagePath || "").replace(/^\/+/, "");
  return `/${relative}?v=${encodeURIComponent(version)}`;
}

function attachCandidateImageError(imagePath, version = "") {
  const image = qs("#artFrame img");
  if (!image) return;

  const directUrl = candidateImageUrl(imagePath, version);
  image.addEventListener("error", () => {
    qs("#artFrame").innerHTML = `
      <div class="placeholder candidate-error">
        <div>
          <strong>Preview could not load.</strong><br><br>
          The generated PNG still exists. 
          <a href="${esc(directUrl)}" target="_blank" rel="noopener">Open generated image directly</a>.
        </div>
      </div>
    `;
  }, {once: true});
}

function render(d) {
  const p = d.current_page;
  const s = d.current_state;
  const c = s.current_candidate;
  const m = d.current_monster_spec;
  const e = d.current_environment_profile;
  const worker = d.generation_worker || {};
  const generating = s.status === "generating" || worker.running;
  const canGenerate = ["queued", "modify_requested", "regenerate_requested", "generation_failed"].includes(s.status)
    && !worker.running
    && Boolean(p.monster_spec_id);

  qs("#bookId").textContent = d.tome.tome_id || "Active Book";
  qs("#bookTitle").textContent = d.tome.title || "Untitled";

  qs("#progress").innerHTML = `
    <div><strong>${d.progress.approved}/${d.progress.total}</strong></div>
    <div>pages approved</div>
    <div id="comfyStatus" class="comfy-status">Checking local artist...</div>
  `;

  qs("#pageHeader").innerHTML = `
    <div>
      <p class="eyebrow">${esc(p.page_id)} · Page ${p.order} of ${d.progress.total}</p>
      <h2>${esc(p.monster_name)}</h2>
      <p class="tagline">${esc(p.habitat)}</p>
    </div>
    <span class="badge">${esc(s.status.replaceAll("_", " "))}</span>
  `;

  if (c?.image_path) {
    const imageUrl = candidateImageUrl(c.image_path, c.created_at || "");
    qs("#artFrame").innerHTML = `
      <img src="${esc(imageUrl)}"
           alt="Current ${esc(p.monster_name)} candidate">
    `;
    attachCandidateImageError(c.image_path, c.created_at || "");
  } else {
    qs("#artFrame").innerHTML = `
      <div class="placeholder">
        <div>
          <strong>${esc(p.page_id)} · ${esc(p.monster_name)}</strong><br><br>
          ${generating ? "Generating locally now..." : "No generated candidate yet."}
        </div>
      </div>
    `;
  }

  const visual = m?.visual_identity || {};
  const ref = m?.reference || {};
  const refImg = ref.resolved_image;
  qs("#referencePanel").innerHTML = m ? `
    <div class="reference-head">
      <div>
        <p class="eyebrow">Canonical Monster Identity</p>
        <h3>${esc(m.monster_name)}</h3>
      </div>
      <span class="identity-badge">${esc(m.family || "monster")}</span>
    </div>
    ${refImg
      ? `<img class="reference-image" src="${esc(refImg)}" alt="Identity reference for ${esc(m.monster_name)}">`
      : `<div class="reference-placeholder"><strong>Identity brief active</strong><span>No reference image loaded yet. Anatomy rules still drive generation.</span></div>`
    }
    <p class="identity-core">${esc(visual.core_identity || "")}</p>
    <dl class="identity-facts">
      <dt>Silhouette</dt><dd>${esc(visual.silhouette || "")}</dd>
      <dt>Head</dt><dd>${esc(visual.head_features || "")}</dd>
      <dt>Body</dt><dd>${esc(visual.body_shape || "")}</dd>
    </dl>
    <h4>Monster Accuracy Check</h4>
    ${list(m.accuracy_checks)}
    <p class="reference-rule">${esc(ref.notes || "Reference art controls anatomy and identity only; Black-Ink controls style.")}</p>
  ` : `
    <div class="reference-placeholder">
      <strong>Canonical spec required</strong>
      <span>This page will not auto-generate until its monster identity spec is ready.</span>
    </div>
  `;

  qs("#brief").innerHTML = `
    <h3>Archetype</h3><p>${esc((p.archetype || "default_scene").replaceAll("_", " "))}</p>
    <h3>Environment Profile</h3>
    <p><strong>${esc(e?.name || p.environment_profile_id || "Unassigned")}</strong></p>
    <p>${esc(e?.description || "")}</p>
    ${e ? list(e.visual_cues) : ""}
    <h3>Unique Background Variant</h3>
    <p><strong>Landmark:</strong> ${esc(p.environment_variant?.landmark || "")}</p>
    <p><strong>Framing:</strong> ${esc(p.environment_variant?.framing || "")}</p>
    <p><strong>Interaction:</strong> ${esc(p.environment_variant?.interaction || "")}</p>
    <h3>Moment</h3><p>${esc(p.moment)}</p>
    <h3>Physicality</h3>
    <p><strong>Mode:</strong> ${esc(p.physicality?.mode || "")}</p>
    <p><strong>Support:</strong> ${esc(p.physicality?.support || "")}</p>
    <p><strong>Motion:</strong> ${esc(p.physicality?.motion || "")}</p>
    <h3>Canonical Identity Checks</h3>${list(m?.accuracy_checks)}
    <h3>Page Recipe</h3>
    <ul>
      <li><strong>Landmark:</strong> ${esc(p.environment_variant?.landmark || "")}</li>
      <li><strong>Framing:</strong> ${esc(p.environment_variant?.framing || "")}</li>
      <li><strong>Interaction:</strong> ${esc(p.environment_variant?.interaction || "")}</li>
    </ul>
    <h3>Must Avoid</h3>${list(p.must_avoid)}
    ${s.review_notes ? `
      <h3>Current Review Direction</h3>
      ${s.review_notes.text ? `<p>${esc(s.review_notes.text)}</p>` : ""}
      ${s.review_notes.quick_tags?.length ? `<p><strong>Quick changes:</strong></p>${list(s.review_notes.quick_tags)}` : ""}
      ${s.review_notes.preserve_dimensions?.length ? `<p><strong>Preserve:</strong></p>${list(s.review_notes.preserve_dimensions)}` : ""}
      ${s.review_notes.failed_dimensions?.length ? `<p><strong>Correct:</strong></p>${list(s.review_notes.failed_dimensions)}` : ""}
    ` : ""}
  `;

  qs("#queue").innerHTML = d.ordered_pages.map((x) => `
    <div class="queue-row ${x.page_id === d.current_page_id ? "current" : ""} ${x.status === "locked" ? "locked" : ""}">
      <span>${esc(x.page_id)}</span>
      <span>${esc(x.monster_name)}</span>
      <span class="state">${esc(x.status)}</span>
    </div>
  `).join("");

  qs("#approve").disabled = !(c && s.status === "awaiting_human") || generating;
  qs("#modify").disabled = !c || generating;
  qs("#regenerate").disabled = !c || generating;
  qs("#generate").disabled = !canGenerate;

  if (generating) {
    qs("#statusLine").innerHTML = `<strong>Generating ${esc(p.monster_name)} locally...</strong> The Studio will refresh when the candidate is ready.`;
  } else if (worker.reason === "local_generation_preflight_failed") {
    const missing = worker.preflight?.required_models_missing || [];
    const detail = missing.length ? ` Missing models: ${missing.join(", ")}.` : "";
    qs("#statusLine").innerHTML = `<span class="error"><strong>Local artist is not generation-ready.</strong>${esc(detail)} Check the readiness status above.</span>`;
  } else if (s.generation_error?.message) {
    qs("#statusLine").innerHTML = `<span class="error"><strong>Generation stopped:</strong> ${esc(s.generation_error.message)}</span>`;
  } else if (c) {
    const mode = c.generation_mode ? ` · Mode: <strong>${esc(c.generation_mode.replaceAll("_", " "))}</strong>` : "";
    const retry = c.technical_retry ? ` · Auto-retries: <strong>${c.technical_retry}</strong>` : "";
    qs("#statusLine").innerHTML = `Attempt <strong>${c.attempt}</strong>${mode}${retry} · QA: <strong>${esc(c.qa_status)}</strong> · Supervisor: <strong>${esc(c.supervisor_status)}</strong>`;
  } else if (!p.monster_spec_id) {
    qs("#statusLine").innerHTML = `<strong>Identity gate:</strong> canonical monster spec required before this page can generate.`;
  } else {
    qs("#statusLine").innerHTML = "<strong>Ready to generate.</strong>";
  }
}

async function refresh({checkArtist = false} = {}) {
  if (refreshing) return;
  refreshing = true;
  try {
    render(await api("/api/state"));
    if (checkArtist) await checkComfy();
  } catch (error) {
    qs("#statusLine").innerHTML = `<span class="error">${esc(error.message)}</span>`;
  } finally {
    refreshing = false;
  }
}

async function decide(decision) {
  try {
    const d = await api("/api/decision", {
      method: "POST",
      body: JSON.stringify({
        decision,
        notes: qs("#notes").value,
        quick_tags: [...selectedTags],
      }),
    });
    qs("#notes").value = "";
    selectedTags.clear();
    document.querySelectorAll("[data-tag]").forEach((b) => b.classList.remove("selected"));
    render(d);
    await checkComfy();
  } catch (error) {
    qs("#statusLine").innerHTML = `<span class="error">${esc(error.message)}</span>`;
  }
}

async function generateNow() {
  try {
    render(await api("/api/generate", {method: "POST", body: "{}"}));
    await checkComfy();
  } catch (error) {
    qs("#statusLine").innerHTML = `<span class="error">${esc(error.message)}</span>`;
  }
}

async function checkComfy() {
  const el = qs("#comfyStatus");
  if (!el) return;
  try {
    const d = await api("/api/local-preflight");
    window.blackInkPreflight = d;
    if (d.ready_for_generation) {
      const gpu = d.devices?.[0]?.name || "GPU detected";
      el.className = "comfy-status comfy-ok";
      el.textContent = "Local artist generation-ready · " + gpu;
      return;
    }
    const failed = Object.entries(d.checks || {}).filter(([, ok]) => !ok).map(([name]) => name);
    const missing = d.required_models_missing || [];
    let detail = failed.join(", ").replaceAll("_", " ");
    if (missing.length) detail = "missing models: " + missing.join(", ");
    el.className = "comfy-status comfy-off";
    el.textContent = "Local artist not ready · " + (detail || "preflight failed");
  } catch {
    window.blackInkPreflight = null;
    el.className = "comfy-status comfy-off";
    el.textContent = "Local artist readiness check failed";
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
setInterval(() => refresh(), 2500);
setInterval(checkComfy, 10000);
