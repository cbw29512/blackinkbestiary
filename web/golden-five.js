let goldenSelectedPageId = null;
let goldenRefreshing = false;
let goldenLastData = null;

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

function goldenSelected(data) {
  const pages = data.pages || [];
  const existing = pages.find((page) => page.page_id === goldenSelectedPageId);
  if (existing) return existing;
  const next = pages.find((page) => page.status !== "locked") || pages[0] || null;
  goldenSelectedPageId = next?.page_id || null;
  return next;
}

function bindGoldenControls(data, page) {
  const root = document.querySelector("#goldenFive");
  if (!root || !page) return;
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

function renderGolden(data) {
  goldenLastData = data;
  const page = goldenSelected(data);
  renderGoldenView(data, page);
  bindGoldenControls(data, page);
}

function goldenError(message) {
  const el = document.querySelector("#goldenError");
  if (el) el.textContent = message;
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
    goldenError(error.message);
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
    goldenError(error.message);
  }
}

refreshGolden();
setInterval(refreshGolden, 2500);
