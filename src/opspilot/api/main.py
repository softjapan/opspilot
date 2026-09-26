"""OpsPilot API: exposes investigations over HTTP + Server-Sent Events.

Reuses `opspilot.investigate.investigate` — the same orchestrator the CLI
uses — so the CLI and Web UI never diverge in behavior. No auth, no
persistence: this is a single-user, localhost-facing v1 API.
"""

from __future__ import annotations

import json
import queue
import threading
import uuid
from dataclasses import asdict
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
_event_queues: dict[str, "queue.Queue[Any]"] = {}


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

    investigation_id = uuid.uuid4().hex
    event_queue: queue.Queue[Any] = queue.Queue()
    _event_queues[investigation_id] = event_queue

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
    event_queue = _event_queues.get(investigation_id)
    if event_queue is None:
        raise HTTPException(status_code=404, detail="Unknown investigation id")

    def event_stream():
        try:
            while True:
                item = event_queue.get()
                if item is _DONE:
                    break
                yield f"data: {json.dumps(item)}\n\n"
        finally:
            _event_queues.pop(investigation_id, None)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
