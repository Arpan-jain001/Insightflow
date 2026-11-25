"""M3 — Model definitions shared by training and serving."""
from __future__ import annotations

import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

from .config import BIN_COLS, CAT_COLS, LIN_COLS, LOG_COLS, RANDOM_SEED


def _linear_preprocessor() -> ColumnTransformer:
    log = Pipeline([("log", FunctionTransformer(np.log1p)), ("sc", StandardScaler())])
    return ColumnTransformer([
        ("log", log, LOG_COLS),
        ("lin", StandardScaler(), LIN_COLS),
        ("bin", "passthrough", BIN_COLS),
        ("cat", OneHotEncoder(handle_unknown="ignore"), CAT_COLS),
    ])


def _tree_preprocessor() -> ColumnTransformer:
    return ColumnTransformer([
        ("num", "passthrough", LOG_COLS + LIN_COLS + BIN_COLS),
        ("cat", OneHotEncoder(handle_unknown="ignore"), CAT_COLS),
    ])


def make_models(seed: int = RANDOM_SEED) -> dict[str, Pipeline]:
    return {
        "logistic_regression": Pipeline([
            ("prep", _linear_preprocessor()),
            ("clf", LogisticRegression(max_iter=2000, C=1.0, random_state=seed)),
        ]),
        "random_forest": Pipeline([
            ("prep", _tree_preprocessor()),
            ("clf", RandomForestClassifier(n_estimators=300, min_samples_leaf=5, n_jobs=2, random_state=seed)),
        ]),
        "xgboost": Pipeline([
            ("prep", _tree_preprocessor()),
            ("clf", XGBClassifier(n_estimators=300, max_depth=4, learning_rate=0.05, subsample=0.8,
                                  colsample_bytree=0.8, eval_metric="logloss", n_jobs=2, random_state=seed)),
        ]),
    }
