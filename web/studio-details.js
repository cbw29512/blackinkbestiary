(() => {
  const {qs, esc, list} = window.BlackInkDom;

  function renderReference(monster) {
    const visual = monster?.visual_identity || {};
    const reference = monster?.reference || {};
    const image = reference.resolved_image;

    qs("#referencePanel").innerHTML = monster ? `
      <div class="reference-head">
        <div>
          <p class="eyebrow">Canonical Monster Identity</p>
          <h3>${esc(monster.monster_name)}</h3>
        </div>
        <span class="identity-badge">${esc(monster.family || "monster")}</span>
      </div>
      ${image
        ? `<img class="reference-image" src="${esc(image)}"
             alt="Identity reference for ${esc(monster.monster_name)}">`
        : `<div class="reference-placeholder">
             <strong>Identity brief active</strong>
             <span>No reference image loaded yet. Anatomy rules still drive generation.</span>
           </div>`
      }
      <p class="identity-core">${esc(visual.core_identity || "")}</p>
      <dl class="identity-facts">
        <dt>Silhouette</dt><dd>${esc(visual.silhouette || "")}</dd>
        <dt>Head</dt><dd>${esc(visual.head_features || "")}</dd>
        <dt>Body</dt><dd>${esc(visual.body_shape || "")}</dd>
      </dl>
      <h4>Monster Accuracy Check</h4>
      ${list(monster.accuracy_checks)}
      <p class="reference-rule">${esc(
        reference.notes ||
        "Reference art controls anatomy and identity only; Black-Ink controls style."
      )}</p>
    ` : `
      <div class="reference-placeholder">
        <strong>Canonical spec required</strong>
        <span>This page will not auto-generate until its monster identity spec is ready.</span>
      </div>
    `;
  }

  function renderBrief(page, state, monster, environment) {
    const review = state.review_notes;
    qs("#brief").innerHTML = `
      <h3>Archetype</h3>
      <p>${esc((page.archetype || "default_scene").replaceAll("_", " "))}</p>
      <h3>Environment Profile</h3>
      <p><strong>${esc(environment?.name || page.environment_profile_id || "Unassigned")}</strong></p>
      <p>${esc(environment?.description || "")}</p>
      ${environment ? list(environment.visual_cues) : ""}
      <h3>Unique Background Variant</h3>
      <p><strong>Landmark:</strong> ${esc(page.environment_variant?.landmark || "")}</p>
      <p><strong>Framing:</strong> ${esc(page.environment_variant?.framing || "")}</p>
      <p><strong>Interaction:</strong> ${esc(page.environment_variant?.interaction || "")}</p>
      <h3>Moment</h3><p>${esc(page.moment)}</p>
      <h3>Physicality</h3>
      <p><strong>Mode:</strong> ${esc(page.physicality?.mode || "")}</p>
      <p><strong>Support:</strong> ${esc(page.physicality?.support || "")}</p>
      <p><strong>Motion:</strong> ${esc(page.physicality?.motion || "")}</p>
      <h3>Canonical Identity Checks</h3>${list(monster?.accuracy_checks)}
      <h3>Must Avoid</h3>${list(page.must_avoid)}
      ${review ? `
        <h3>Current Review Direction</h3>
        ${review.text ? `<p>${esc(review.text)}</p>` : ""}
        ${review.quick_tags?.length
          ? `<p><strong>Quick changes:</strong></p>${list(review.quick_tags)}`
          : ""}
        ${review.preserve_dimensions?.length
          ? `<p><strong>Preserve:</strong></p>${list(review.preserve_dimensions)}`
          : ""}
        ${review.failed_dimensions?.length
          ? `<p><strong>Correct:</strong></p>${list(review.failed_dimensions)}`
          : ""}
      ` : ""}
    `;
  }

  window.BlackInkDetails = {renderReference, renderBrief};
})();
