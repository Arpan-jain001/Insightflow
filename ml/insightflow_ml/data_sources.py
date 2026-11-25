"""M1 — Where raw events come from. Every loader returns the RAW canonical schema:

    anonymous_id | user_id | event_name | ts (UTC) | page | referrer | ua | scroll_depth

Cleaning / identity resolution / sessionisation happen later in cleaning.py.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

RAW_COLUMNS = ["anonymous_id", "user_id", "event_name", "ts", "page", "referrer", "ua", "scroll_depth"]


# --------------------------------------------------------------------------- MongoDB
def load_from_mongo(mongo_uri: str, project_id: str | None = None, since=None,
                    db_name: str | None = None, batch_size: int = 5000) -> pd.DataFrame:
    from bson import ObjectId
    from pymongo import MongoClient

    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=8000)
    db = client[db_name] if db_name else client.get_default_database()
    query: dict = {}
    if project_id:
        query["projectId"] = ObjectId(project_id)
    if since is not None:
        query["ts"] = {"$gte": pd.Timestamp(since).to_pydatetime()}
    proj = {
        "anonymousId": 1, "userId": 1, "eventName": 1, "ts": 1, "ua": 1,
        "properties.page": 1, "properties.referrer": 1,
        "properties.scrollDepth": 1, "properties.scroll_depth": 1,
    }
    rows = []
    for d in db["events"].find(query, proj).batch_size(batch_size):
        p = d.get("properties") or {}
        rows.append((
            d.get("anonymousId", ""), d.get("userId", ""), d.get("eventName", ""), d.get("ts"),
            p.get("page", ""), p.get("referrer", ""), d.get("ua", ""),
            p.get("scrollDepth", p.get("scroll_depth")),
        ))
    client.close()
    return pd.DataFrame(rows, columns=RAW_COLUMNS)


# --------------------------------------------------------------------------- CSV
def load_from_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = set(RAW_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing columns: {sorted(missing)}")
    return df[RAW_COLUMNS]


# --------------------------------------------------------------------------- Public dataset adapter
def adapt_rees46(csv_path: str, max_rows: int | None = None) -> pd.DataFrame:
    """REES46 'eCommerce behavior data from multi category store' (Kaggle).

    Columns: event_time,event_type,product_id,category_id,category_code,brand,price,user_id,user_session
    Real human behaviour -> the right dataset to report model quality on.
    view->page_view, cart->add_to_cart, purchase->purchase, remove_from_cart->click
    """
    df = pd.read_csv(csv_path, nrows=max_rows)
    name_map = {"view": "page_view", "cart": "add_to_cart", "purchase": "purchase", "remove_from_cart": "click"}
    out = pd.DataFrame({
        "anonymous_id": df["user_id"].astype(str),
        "user_id": "",
        "event_name": df["event_type"].map(name_map).fillna("click"),
        "ts": pd.to_datetime(df["event_time"], utc=True, errors="coerce"),
        "page": df["category_code"].fillna("/unknown").astype(str),
        "referrer": "",
        "ua": "Mozilla/5.0 (Windows NT 10.0) Chrome/124.0",
        "scroll_depth": np.nan,
    })
    return out[RAW_COLUMNS]


# --------------------------------------------------------------------------- Synthetic
_REFERRERS = {"direct": "", "search": "https://www.google.com/",
              "social": "https://www.linkedin.com/", "other": "https://news.example.org/"}
_SRC_EFFECT = {"direct": 0.3, "search": 0.0, "social": -0.2, "other": -0.4}
_PAGES = ["/", "/features", "/pricing", "/blog", "/signup", "/dashboard", "/docs", "/contact"]
_UA_DESKTOP = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0"
_UA_MOBILE = "Mozilla/5.0 (Linux; Android 14) Chrome/123.0 Mobile"


def generate_synthetic(n_visitors: int = 4000, days: int = 60, seed: int = 7, end=None) -> pd.DataFrame:
    """SYNTHETIC data for pipeline testing and demos ONLY.

    The return probability is a known function of engagement + noise, so a model
    reaching AUC ~0.7 here only proves the pipeline works. It says NOTHING about real
    visitors. Never report these numbers as research results.
    """
    rng = np.random.default_rng(seed)
    end = pd.Timestamp(end) if end is not None else pd.Timestamp.now(tz="UTC").floor("h")
    if end.tzinfo is None:
        end = end.tz_localize("UTC")
    start = end - pd.Timedelta(days=days)
    srcs = list(_SRC_EFFECT)
    rows: list[tuple] = []

    def session(anon, user, t, e, mobile, ref, n_pages, conv):
        ua = _UA_MOBILE if mobile else _UA_DESKTOP
        cur, prev_page = t, ""
        for i in range(n_pages):
            page = _PAGES[int(rng.integers(0, len(_PAGES)))]
            rows.append((anon, user, "page_view", cur, page, ref if i == 0 else prev_page, ua, np.nan))
            if rng.random() < 0.25 + 0.6 * e:
                cur += pd.Timedelta(seconds=float(rng.uniform(3, 25)))
                depth = float(np.clip(rng.normal(30 + 60 * e, 20), 5, 100))
                rows.append((anon, user, "scroll_depth", cur, page, ref, ua, depth))
            for _ in range(int(rng.poisson(1.5 * e))):
                cur += pd.Timedelta(seconds=float(rng.uniform(2, 20)))
                rows.append((anon, user, "button_click", cur, page, ref, ua, np.nan))
            prev_page = page
            cur += pd.Timedelta(seconds=float(rng.lognormal(3.0 + 0.8 * e, 0.6)))
        if conv:
            rows.append((anon, user, "signup", cur, "/signup", ref, ua, np.nan))

    for v in range(n_visitors):
        anon = f"anon_{seed}_{v}"
        e = float(rng.beta(2, 3))
        mobile = bool(rng.random() < 0.55)
        src = srcs[int(rng.choice(len(srcs), p=[0.3, 0.4, 0.2, 0.1]))]
        t0 = start + pd.Timedelta(seconds=float(rng.uniform(0, days * 86400)))
        identified = rng.random() < 0.15
        user = f"user_{seed}_{v}" if identified else ""
        conv = rng.random() < 0.02 + 0.25 * e ** 2
        n_pages = 1 + int(rng.poisson(0.5 + 5 * e))
        session(anon, user, t0, e, mobile, _REFERRERS[src], n_pages, conv)

        logit = -1.6 + 3.0 * e + 0.5 * conv + _SRC_EFFECT[src] - 0.2 * mobile + rng.normal(0, 0.9)
        if rng.random() < 1 / (1 + np.exp(-logit)):
            d1 = int(rng.integers(1, 7))
            offsets = [d1] + [int(x) for x in rng.integers(1, 30, size=int(rng.poisson(1)))]
            for d in offsets:
                tr = t0 + pd.Timedelta(days=d, hours=float(rng.uniform(0, 12)))
                if tr <= end:
                    session(anon, user, tr, e, mobile, "", 1 + int(rng.poisson(1 + 3 * e)), False)

    for b in range(int(n_visitors * 0.03)):  # bots, removed by cleaning
        t = start + pd.Timedelta(seconds=float(rng.uniform(0, days * 86400)))
        rows.append((f"bot_{b}", "", "page_view", t, "/", "", "Mozilla/5.0 (compatible; Googlebot/2.1)", np.nan))

    df = pd.DataFrame(rows, columns=RAW_COLUMNS)
    df = pd.concat([df, df.sample(frac=0.01, random_state=seed)], ignore_index=True)  # duplicates
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return df[df["ts"] <= end].sort_values("ts").reset_index(drop=True)
