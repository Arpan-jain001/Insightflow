import numpy as np
import pandas as pd
import pytest

from insightflow_ml import config as C
from insightflow_ml.cleaning import prepare_events, resolve_identity
from insightflow_ml.data_sources import RAW_COLUMNS, generate_synthetic
from insightflow_ml.features import build_visitor_table

T0 = pd.Timestamp("2026-01-01 10:00", tz="UTC")


def ev(anon, minutes=0, days=0, name="page_view", user="", page="/", ua="Chrome", ref="", scroll=np.nan):
    return (anon, user, name, T0 + pd.Timedelta(days=days, minutes=minutes), page, ref, ua, scroll)


def build(rows, as_of):
    ev_, _ = prepare_events(pd.DataFrame(rows, columns=RAW_COLUMNS))
    return build_visitor_table(ev_, as_of=as_of).set_index("visitor_id")


def test_label_true_when_return_next_day_within_window():
    vt = build([ev("a"), ev("a", 2), ev("a", days=2)], as_of=T0 + pd.Timedelta(days=30))
    assert vt.loc["a", C.TARGET] == 1 and vt.loc["a", "label_known"]


def test_same_day_second_session_is_not_retention():
    vt = build([ev("a"), ev("a", minutes=300)], as_of=T0 + pd.Timedelta(days=30))
    assert vt.loc["a", C.TARGET] == 0


def test_return_after_window_is_not_retention():
    vt = build([ev("a"), ev("a", days=9)], as_of=T0 + pd.Timedelta(days=30))
    assert vt.loc["a", C.TARGET] == 0


def test_features_do_not_leak_future_events():
    base = [ev("a"), ev("a", 1, name="button_click")]
    later = base + [ev("a", days=2), ev("a", days=2, minutes=1, name="signup")]
    a = build(base, T0 + pd.Timedelta(days=30)).loc["a"]
    b = build(later, T0 + pd.Timedelta(days=30)).loc["a"]
    for c in C.FEATURE_COLUMNS:
        assert a[c] == b[c], f"feature {c} changed when only later events were added"


def test_unfinished_window_is_label_unknown():
    vt = build([ev("a")], as_of=T0 + pd.Timedelta(days=3))
    assert not vt.loc["a", "label_known"]


def test_identity_resolution_links_anon_to_user():
    df = pd.DataFrame([ev("anon1"), ev("anon1", 1, user="u1"), ev("anon1", days=1)], columns=RAW_COLUMNS)
    assert set(resolve_identity(df).visitor_id) == {"u1"}


def test_bots_and_duplicates_removed():
    rows = [ev("a"), ev("a"), ev("bot", ua="Googlebot/2.1")]
    _, rep = prepare_events(pd.DataFrame(rows, columns=RAW_COLUMNS))
    assert rep["dropped_bots"] == 1 and rep["dropped_duplicates"] == 1


@pytest.fixture(scope="module")
def trained(tmp_path_factory):
    from insightflow_ml.train import train_model
    ev_, _ = prepare_events(generate_synthetic(n_visitors=2500, seed=3))
    out = tmp_path_factory.mktemp("art")
    meta = train_model(build_visitor_table(ev_), "synthetic", out_dir=out)
    return meta, out


def test_models_beat_chance_and_no_perfect_score(trained):
    meta, _ = trained
    auc = meta["results"][meta["best_model"]]["test"]["roc_auc"]
    assert 0.55 < auc < 0.95          # AUC ~1.0 would signal leakage
    assert meta["is_synthetic"]


def test_refuses_tiny_dataset():
    from insightflow_ml.train import train_model
    ev_, _ = prepare_events(generate_synthetic(n_visitors=60, seed=1))
    with pytest.raises(ValueError):
        train_model(build_visitor_table(ev_), "synthetic")


def test_api_end_to_end(trained, monkeypatch):
    from fastapi.testclient import TestClient
    from insightflow_ml import api
    from insightflow_ml.predict import load_model
    _, out = trained
    api._state["model"], api._state["meta"] = load_model(out)
    monkeypatch.setenv("ML_API_KEY", "secret")
    c = TestClient(api.app)
    assert c.get("/health").json()["model_loaded"]
    assert c.post("/predict/events", json={"events": []}).status_code == 401
    raw = generate_synthetic(n_visitors=300, days=10, seed=11)
    raw["ts"] = raw["ts"].astype(str)
    r = c.post("/predict/events", headers={"x-ml-key": "secret"},
               json={"events": raw.replace({np.nan: None}).to_dict("records")})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ok" and sum(r.json()["buckets"].values()) > 0
