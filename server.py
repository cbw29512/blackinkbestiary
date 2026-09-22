from __future__ import annotations

import argparse
import threading
import webbrowser
from http.server import ThreadingHTTPServer

from art_pipeline.studio_candidates import register_candidate
from art_pipeline.studio_http import Handler
from art_pipeline.studio_production import (
    VALID_DECISIONS,
    apply_decision,
    public_state,
)
from art_pipeline.studio_store import (
    APPROVED_ROOT,
    REVIEWS_FILE,
    STATE_FILE,
    WEB_DIR,
    load_state,
    load_tome,
    read_json,
    validate_state,
    write_json,
)
from art_pipeline.studio_worker import (
    GENERATOR_LOG,
    GENERATOR_SCRIPT,
    GENERATABLE_STATES,
    comfy_health,
    generation_worker_status,
    start_generation_worker,
)


def run(host="127.0.0.1", port=8765, open_browser=True):
    validate_state(load_tome(), load_state())
    server = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}"
    print(f"Black-Ink Bestiary Studio: {url}")
    print("Press Ctrl+C to stop.")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Black-Ink Bestiary local production studio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    run(args.host, args.port, not args.no_browser)
