(() => {
  const qs = (selector) => document.querySelector(selector);

  function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, (char) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    }[char]));
  }

  function list(items) {
    return `<ul>${(items || [])
      .map((item) => `<li>${esc(item)}</li>`)
      .join("")}</ul>`;
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
            <a href="${esc(directUrl)}" target="_blank" rel="noopener">
              Open generated image directly
            </a>.
          </div>
        </div>
      `;
    }, {once: true});
  }

  window.BlackInkDom = {
    qs,
    esc,
    list,
    candidateImageUrl,
    attachCandidateImageError,
  };
})();
