"""M4 — FastAPI service. Run:  uvicorn insightflow_ml.api:app --port 8001

Only the Node backend should call this (shared secret in x-ml-key). It is NOT for browsers.
"""
from __future__ import annotations

import hmac
import os
import threading

import pandas as pd
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from . import config as C
from .data_sources import RAW_COLUMNS, load_from_mongo
from .cleaning import prepare_events
from .features import build_visitor_table
from .predict import load_model, summarize
from .train import train_model

app = FastAPI(title="InsightFlow ML", version="1.0")
_state = {"model": None, "meta": None, "training": "idle", "error": None}
_lock = threading.Lock()


def _reload():
    _state["model"], _state["meta"] = load_model()


_reload()


def require_key(x_ml_key: str | None = Header(default=None)):
    expected = os.getenv("ML_API_KEY", "")
    if not expected:
        raise HTTPException(503, "ML_API_KEY not configured")  # fail closed
    if not x_ml_key or not hmac.compare_digest(x_ml_key, expected):
        raise HTTPException(401, "invalid key")


class ProjectReq(BaseModel):
    projectId: str


class EventsReq(BaseModel):
    events: list[dict]


class TrainReq(BaseModel):
    projectId: str | None = None


@app.get("/health")
def health():
    return {"ok": True, "model_loaded": _state["model"] is not None, "training": _state["training"]}


@app.get("/model", dependencies=[Depends(require_key)])
def model_info():
    if _state["meta"] is None:
        raise HTTPException(404, "no trained model")
    m = dict(_state["meta"]); m.pop("permutation_importance", None)
    return m


@app.post("/predict/project", dependencies=[Depends(require_key)])
def predict_project(req: ProjectReq):
    if _state["model"] is None:
        raise HTTPException(409, "model not trained yet")
    since = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=C.LOOKBACK_DAYS)
    try:
        raw = load_from_mongo(os.environ["MONGO_URI"], req.projectId, since, os.getenv("MONGO_DB") or None)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"database error: {type(e).__name__}")
    return summarize(raw, _state["model"], _state["meta"])


@app.post("/predict/events", dependencies=[Depends(require_key)])
def predict_events(req: EventsReq):
    """Score a posted batch of raw events (used for tests/demos)."""
    if _state["model"] is None:
        raise HTTPException(409, "model not trained yet")
    if not 0 < len(req.events) <= 50_000:
        raise HTTPException(422, "1..50000 events")
    df = pd.DataFrame(req.events).reindex(columns=RAW_COLUMNS)
    return summarize(df, _state["model"], _state["meta"])


def _train_job(project_id):
    try:
        with _lock:
            _state["training"], _state["error"] = "running", None
            raw = load_from_mongo(os.environ["MONGO_URI"], project_id, None, os.getenv("MONGO_DB") or None)
            ev, _ = prepare_events(raw)
            train_model(build_visitor_table(ev), f"mongo:{project_id or 'all'}")
            _reload()
            _state["training"] = "idle"
    except Exception as e:  # noqa: BLE001
        _state["training"], _state["error"] = "failed", str(e)[:300]


@app.post("/train", dependencies=[Depends(require_key)])
def train(req: TrainReq, bg: BackgroundTasks):
    if _state["training"] == "running":
        raise HTTPException(409, "training already running")
    bg.add_task(_train_job, req.projectId)
    return {"started": True}


@app.get("/train/status", dependencies=[Depends(require_key)])
def train_status():
    return {"training": _state["training"], "error": _state["error"]}
