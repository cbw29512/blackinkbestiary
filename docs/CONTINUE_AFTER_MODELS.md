# Continue After Models

After the verified FLUX.2 Klein model files finish downloading into the **Black-Ink Bestiary ComfyUI Desktop instance**:

1. Close and reopen that ComfyUI Desktop instance so it rescans the model folders.
2. Confirm ComfyUI is running on `127.0.0.1:8188`.
3. Double-click `CONTINUE_AFTER_MODELS.bat`.

This one command:

- uses the already-installed ComfyUI Desktop instance
- does **not** install another ComfyUI workspace
- does **not** redownload the model files
- prepares the small project-local `comfy-cli` control environment
- verifies the GPU and all three required models through the running ComfyUI API
- fetches and validates the current official FLUX.2 Klein workflow templates
- generates exactly one I-01 calibration candidate
- runs the basic candidate QA
- registers the candidate in the Black-Ink Bestiary Studio
- opens the Studio for human review

The queue remains locked on I-01 unless the human clicks **APPROVE & LOCK**.

If any step fails, the window stays open and the page order does not advance.
