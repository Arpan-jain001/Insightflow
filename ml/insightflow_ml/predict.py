"""M4 — Scoring + the project summary the dashboard and Gemini consume."""
from __future__ import annotations

import json
import os

import joblib
import pandas as pd

from . import config as C
from .cleaning import prepare_events
from .features import build_visitor_table


def load_model(dir_=C.ARTIFACT_DIR):
    mp, jp = os.path.join(dir_, "model.joblib"), os.path.join(dir_, "metadata.json")
    if not (os.path.exists(mp) and os.path.exists(jp)):
        return None, None
    with open(jp) as f:
        return joblib.load(mp), json.load(f)


def _bucket(p: float) -> str:
    return "low" if p < 0.33 else "medium" if p < 0.66 else "high"


def summarize(raw_events: pd.DataFrame, model, meta, as_of=None) -> dict:
    ev, report = prepare_events(raw_events)
    vt = build_visitor_table(ev, as_of=as_of or pd.Timestamp.now(tz="UTC"))
    base = {
        "model": {
            "name": meta["best_model"], "trained_at": meta["trained_at"],
            "trained_on": meta["data_source"], "is_synthetic": meta["is_synthetic"],
            "test_roc_auc": meta["results"][meta["best_model"]]["test"]["roc_auc"],
            "test_pr_auc": meta["results"][meta["best_model"]]["test"]["pr_auc"],
            "label": meta["label"],
            "beats_baseline": meta["results"][meta["best_model"]]["test"]["roc_auc"]
                              > meta["results"]["baseline_rule_pageviews"]["test"]["roc_auc"],
        },
        "cleaning": report, "top_drivers": meta["permutation_importance"][:6],
    }
    if vt.empty:
        return {**base, "status": "no_data"}
    known, pending = vt[vt.label_known], vt[~vt.label_known].copy()
    base["counts"] = {"visitors": int(len(vt)), "pending_scored": int(len(pending)), "labelled": int(len(known))}
    base["observed_return_rate_7d"] = round(float(known[C.TARGET].mean()), 4) if len(known) >= 30 else None
    if pending.empty:
        return {**base, "status": "no_recent_visitors"}

    pending["p_return"] = model.predict_proba(pending[C.FEATURE_COLUMNS])[:, 1]
    pending["bucket"] = pending.p_return.map(_bucket)
    seg = {}
    for col in ("referrer_type", "is_mobile"):
        g = pending.groupby(col).p_return.agg(["mean", "size"])
        seg[col] = [{"segment": str(k), "visitors": int(r["size"]), "avg_return_probability": round(float(r["mean"]), 3)}
                    for k, r in g.iterrows() if r["size"] >= 5]
    return {**base, "status": "ok",
            "avg_return_probability": round(float(pending.p_return.mean()), 3),
            "buckets": {b: int((pending.bucket == b).sum()) for b in ("low", "medium", "high")},
            "segments": seg}
