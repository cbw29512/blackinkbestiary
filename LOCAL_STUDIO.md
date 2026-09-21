# Local Studio — v1

## Start

On Windows, double-click:

`START_STUDIO.bat`

Or run:

```bash
python server.py
```

The studio opens at `http://127.0.0.1:8765`.

## What v1 Does Now

- loads the 50-page Tome I manifest
- enforces one active page at a time
- keeps page order locked
- persists production state to JSON
- records APPROVE / MODIFY / REGENERATE decisions
- refuses approval unless a real current candidate has been registered
- advances exactly one page only after approval
- preserves attempt history

## Candidate Registration Contract

The local art worker will register its chosen candidate with:

`POST /api/candidate`

Example:

```json
{
  "page_id": "I-01",
  "image_path": "candidates/I-01-A001.png",
  "qa_status": "pass",
  "supervisor_status": "ready_for_human"
}
```

Generator integration comes next. The review/state loop is deliberately built first so the AI cannot skip pages or overwrite approved work.
