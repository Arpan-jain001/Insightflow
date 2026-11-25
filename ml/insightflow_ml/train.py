"""M3 — Train, compare and save the retention model.

    python -m insightflow_ml.train --source synthetic
    python -m insightflow_ml.train --source csv --path data/events.csv
    python -m insightflow_ml.train --source mongo --project-id <id>
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import (average_precision_score, balanced_accuracy_score, brier_score_loss,
                             confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import StratifiedKFold, cross_val_predict, cross_validate

from . import config as C
from .cleaning import prepare_events
from .features import build_visitor_table
from .modeling import make_models


def purged_temporal_split(vt: pd.DataFrame, test_frac: float = 0.25):
    """Train on earlier visitors, test on later ones, with a purge gap equal to the label window
    so no training label is computed from days that overlap the test period."""
    vt = vt.sort_values("first_seen")
    cutoff = vt.first_seen.quantile(1 - test_frac)
    train = vt[vt.first_seen <= cutoff - pd.Timedelta(days=C.LABEL_WINDOW_DAYS)]
    test = vt[vt.first_seen > cutoff]
    return train, test


def _best_f1_threshold(y, p) -> float:
    grid = np.linspace(0.05, 0.95, 91)
    return float(grid[int(np.argmax([f1_score(y, p >= t, zero_division=0) for t in grid]))])


def _metrics(y, p, thr) -> dict:
    pred = p >= thr
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    return {
        "roc_auc": float(roc_auc_score(y, p)), "pr_auc": float(average_precision_score(y, p)),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "brier": float(brier_score_loss(y, p)), "threshold": thr,
        "confusion": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }


def _boot_auc(y, p, rng, n=500):
    idx = [rng.integers(0, len(y), len(y)) for _ in range(n)]
    return idx, np.array([roc_auc_score(y[i], p[i]) if len(set(y[i])) == 2 else np.nan for i in idx])


def train_model(vt: pd.DataFrame, data_source: str, out_dir=C.ARTIFACT_DIR, seed: int = C.RANDOM_SEED) -> dict:
    known = vt[vt.label_known]
    if len(known) < C.MIN_TRAIN_ROWS or known[C.TARGET].nunique() < 2:
        raise ValueError(f"Need >= {C.MIN_TRAIN_ROWS} labelled visitors with both classes; "
                         f"have {len(known)}. Collect more data — do not lower this limit.")
    train, test = purged_temporal_split(known)
    if len(test) < 50 or test[C.TARGET].nunique() < 2 or train[C.TARGET].nunique() < 2:
        raise ValueError("Train/test split too small or single-class.")
    Xtr, ytr = train[C.FEATURE_COLUMNS], train[C.TARGET].to_numpy()
    Xte, yte = test[C.FEATURE_COLUMNS], test[C.TARGET].to_numpy()
    rng = np.random.default_rng(seed)
    cv = StratifiedKFold(5, shuffle=True, random_state=seed)

    results, fitted, test_probs = {}, {}, {}
    # baselines: if the ML models cannot beat these, the ML adds nothing
    prior = DummyClassifier(strategy="prior").fit(Xtr, ytr).predict_proba(Xte)[:, 1]
    results["baseline_prior"] = {"test": {"roc_auc": 0.5, "pr_auc": float(yte.mean()), "brier": float(brier_score_loss(yte, prior))}}
    rule = np.clip(Xte["n_page_views"].to_numpy(), 0, 10) / 10.0
    results["baseline_rule_pageviews"] = {"test": {"roc_auc": float(roc_auc_score(yte, rule)),
                                                  "pr_auc": float(average_precision_score(yte, rule))}}

    for name, pipe in make_models(seed).items():
        cvs = cross_validate(pipe, Xtr, ytr, cv=cv, scoring=["roc_auc", "average_precision"])
        oof = cross_val_predict(pipe, Xtr, ytr, cv=cv, method="predict_proba")[:, 1]
        thr = _best_f1_threshold(ytr, oof)            # tuned on train folds only
        pipe.fit(Xtr, ytr)
        p = pipe.predict_proba(Xte)[:, 1]
        idx, aucs = _boot_auc(yte, p, rng)
        results[name] = {
            "cv_roc_auc_mean": float(cvs["test_roc_auc"].mean()), "cv_roc_auc_std": float(cvs["test_roc_auc"].std()),
            "cv_pr_auc_mean": float(cvs["test_average_precision"].mean()),
            "test": _metrics(yte, p, thr),
            "test_roc_auc_ci95": [float(np.nanpercentile(aucs, 2.5)), float(np.nanpercentile(aucs, 97.5))],
        }
        fitted[name], test_probs[name] = pipe, (p, idx)

    ranked = sorted(fitted, key=lambda n: results[n]["cv_roc_auc_mean"], reverse=True)   # select on CV, never on test
    best, runner = ranked[0], ranked[1]
    pb, idx = test_probs[best]
    pr = test_probs[runner][0]
    diffs = np.array([roc_auc_score(yte[i], pb[i]) - roc_auc_score(yte[i], pr[i]) for i in idx if len(set(yte[i])) == 2])
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    imp = permutation_importance(fitted[best], Xte, yte, scoring="roc_auc", n_repeats=10, random_state=seed, n_jobs=1)
    importance = sorted(
        [{"feature": f, "importance": float(m)} for f, m in zip(C.FEATURE_COLUMNS, imp.importances_mean)],
        key=lambda d: d["importance"], reverse=True)

    meta = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "data_source": data_source, "is_synthetic": data_source.startswith("synthetic"),
        "best_model": best, "selection_rule": "highest 5-fold CV ROC-AUC on the training split",
        "best_vs_runner_up": {"runner_up": runner, "auc_diff_ci95": [float(lo), float(hi)],
                              "statistically_distinguishable": bool(lo > 0 or hi < 0)},
        "label": f"returned on a later calendar day within {C.LABEL_WINDOW_DAYS} days of first visit",
        "features_from": "first session only", "feature_columns": C.FEATURE_COLUMNS,
        "n_visitors_total": int(len(vt)), "n_labelled": int(len(known)), "n_train": int(len(train)), "n_test": int(len(test)),
        "positive_rate_train": float(ytr.mean()), "positive_rate_test": float(yte.mean()),
        "split": "purged temporal (train earlier, test later, gap = label window)",
        "results": results, "permutation_importance": importance,
    }
    os.makedirs(out_dir, exist_ok=True)
    joblib.dump(fitted[best], os.path.join(out_dir, "model.joblib"))
    with open(os.path.join(out_dir, "metadata.json"), "w") as f:
        json.dump(meta, f, indent=2)
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["synthetic", "csv", "mongo", "rees46"], default="synthetic")
    ap.add_argument("--path"); ap.add_argument("--project-id")
    ap.add_argument("--max-rows", type=int)
    a = ap.parse_args()
    from . import data_sources as D
    if a.source == "synthetic":
        raw, label = D.generate_synthetic(), "synthetic"
    elif a.source == "csv":
        raw, label = D.load_from_csv(a.path), f"csv:{os.path.basename(a.path)}"
    elif a.source == "rees46":
        raw, label = D.adapt_rees46(a.path, a.max_rows), "public:rees46"
    else:
        raw = D.load_from_mongo(os.environ["MONGO_URI"], a.project_id, db_name=os.getenv("MONGO_DB") or None)
        label = f"mongo:{a.project_id or 'all'}"
    ev, rep = prepare_events(raw)
    print("cleaning:", rep)
    meta = train_model(build_visitor_table(ev), label)
    for n, r in meta["results"].items():
        print(f"{n:26s} test AUC {r['test'].get('roc_auc', float('nan')):.3f}")
    print("best:", meta["best_model"], "| distinguishable from runner-up:",
          meta["best_vs_runner_up"]["statistically_distinguishable"])


if __name__ == "__main__":
    main()
