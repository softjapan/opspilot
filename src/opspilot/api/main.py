"""OpsPilot API: exposes investigations over HTTP + Server-Sent Events.

Reuses `opspilot.investigate.investigate` — the same orchestrator the CLI
uses — so the CLI and Web UI never diverge in behavior. No auth, no
persistence: this is a single-user, localhost-facing v1 API.
"""

from __future__ import annotations

import json
import queue
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from opspilot.investigate import investigate
from opspilot.targets import get_target

app = FastAPI(title="OpsPilot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_DONE = object()

# How long an investigation's queue is kept if nobody ever streams its
# events (e.g. a client that POSTs and never connects to the SSE endpoint).
# There's no auth/persistence in v1, so this lazy sweep — run on every new
# POST — is enough to keep memory bounded without a background thread.
_ABANDONED_TTL_SECONDS = 300.0


@dataclass
class _Investigation:
    event_queue: "queue.Queue[Any]"
    created_at: float


_investigations: dict[str, _Investigation] = {}


def _evict_abandoned_investigations() -> None:
    cutoff = time.monotonic() - _ABANDONED_TTL_SECONDS
    stale_ids = [inv_id for inv_id, inv in _investigations.items() if inv.created_at < cutoff]
    for inv_id in stale_ids:
        _investigations.pop(inv_id, None)


class InvestigationRequest(BaseModel):
    target: str = "demo"
    question: str = "Why is this slow?"


class InvestigationCreated(BaseModel):
    id: str


@app.post("/investigations", response_model=InvestigationCreated)
def create_investigation(body: InvestigationRequest) -> InvestigationCreated:
    try:
        inv_target = get_target(body.target)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _evict_abandoned_investigations()

    investigation_id = uuid.uuid4().hex
    event_queue: queue.Queue[Any] = queue.Queue()
    _investigations[investigation_id] = _Investigation(event_queue=event_queue, created_at=time.monotonic())

    def on_progress(step: str) -> None:
        event_queue.put({"type": "progress", "step": step})

    def worker() -> None:
        try:
            report = investigate(inv_target, body.question, on_progress=on_progress)
            event_queue.put({"type": "report", "report": asdict(report)})
        except Exception as exc:  # noqa: BLE001 - surface any analyzer/LLM failure to the client
            event_queue.put({"type": "error", "message": str(exc)})
        finally:
            event_queue.put(_DONE)

    threading.Thread(target=worker, daemon=True).start()
    return InvestigationCreated(id=investigation_id)


@app.get("/investigations/{investigation_id}/events")
def stream_events(investigation_id: str) -> StreamingResponse:
    investigation = _investigations.get(investigation_id)
    if investigation is None:
        raise HTTPException(status_code=404, detail="Unknown investigation id")

    def event_stream():
        try:
            while True:
                item = investigation.event_queue.get()
                if item is _DONE:
                    break
                yield f"data: {json.dumps(item)}\n\n"
        finally:
            _investigations.pop(investigation_id, None)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
