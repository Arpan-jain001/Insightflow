"""M2 — Visitor table: leakage-safe features + the retention label.

Rules that keep the model honest (tests in tests/test_features.py enforce them):
 1. Features use ONLY the visitor's FIRST session.
 2. The label uses ONLY events on a LATER calendar day than that session's end,
    within LABEL_WINDOW_DAYS of the first event.
 3. Visitors whose 7-day window is not finished yet have label_known=False.
    They are never used for training (they would all look like "did not return").
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import (CLICK_EVENTS, CONVERSION_EVENTS, FRICTION_PATTERN, INTENT_EVENTS,
                     LABEL_WINDOW_DAYS, SCROLL_EVENTS, TARGET)

_SEARCH = r"google\.|bing\.|duckduckgo\.|yahoo\.|baidu\."
_SOCIAL = r"facebook\.|instagram\.|twitter\.|t\.co|x\.com|linkedin\.|reddit\.|youtube\.|whatsapp|telegram"


def _referrer_type(ref: pd.Series) -> pd.Series:
    r = ref.fillna("").str.lower()
    out = pd.Series("other", index=r.index)
    out[r.str.contains(_SOCIAL, regex=True)] = "social"
    out[r.str.contains(_SEARCH, regex=True)] = "search"
    out[r == ""] = "direct"
    return out


def build_visitor_table(events: pd.DataFrame, as_of=None,
                        window_days: int = LABEL_WINDOW_DAYS) -> pd.DataFrame:
    """events must come from cleaning.prepare_events()."""
    if events.empty:
        return pd.DataFrame()
    window = pd.Timedelta(days=window_days)
    as_of = pd.Timestamp(as_of) if as_of is not None else events["ts"].max()
    if as_of.tzinfo is None:
        as_of = as_of.tz_localize("UTC")

    first = events[events.session_idx == 0].copy()
    name = first.event_name
    first["is_pv"] = name == "page_view"
    first["is_click"] = name.isin(CLICK_EVENTS)
    first["is_scroll"] = name.isin(SCROLL_EVENTS)
    first["is_conv"] = name.isin(CONVERSION_EVENTS)
    first["is_intent"] = name.isin(INTENT_EVENTS)
    first["is_friction"] = name.str.contains(FRICTION_PATTERN, case=False, regex=True)
    first["is_ident"] = first.user_id != ""
    first["page_nz"] = first.page.replace("", np.nan)

    g = first.groupby("visitor_id", sort=False)
    t = g.agg(
        first_seen=("ts", "min"), first_end=("ts", "max"), n_events=("ts", "size"),
        n_page_views=("is_pv", "sum"), n_clicks=("is_click", "sum"),
        n_scroll_events=("is_scroll", "sum"), has_conversion=("is_conv", "max"),
        n_intent_events=("is_intent", "sum"), n_friction_events=("is_friction", "sum"),
        n_unique_pages=("page_nz", "nunique"), n_event_types=("event_name", "nunique"),
        max_scroll_depth=("scroll_depth", "max"), is_identified=("is_ident", "max"),
        first_referrer=("referrer", "first"), first_ua=("ua", "first"),
    )
    t["max_scroll_depth"] = t.max_scroll_depth.fillna(0).clip(0, 100)
    t["duration_sec"] = (t.first_end - t.first_seen).dt.total_seconds()
    t["events_per_min"] = t.n_events / np.maximum(t.duration_sec / 60.0, 1.0)
    hour = t.first_seen.dt.hour + t.first_seen.dt.minute / 60.0
    t["hour_sin"] = np.sin(2 * np.pi * hour / 24)
    t["hour_cos"] = np.cos(2 * np.pi * hour / 24)
    t["is_weekend"] = t.first_seen.dt.dayofweek >= 5
    t["is_mobile"] = t.first_ua.str.contains(r"mobile|android|iphone|ipad", case=False, regex=True)
    t["referrer_type"] = _referrer_type(t.first_referrer)
    t["bounced"] = t.n_events <= 1
    for c in ("has_conversion", "is_identified", "is_mobile", "is_weekend", "bounced"):
        t[c] = t[c].astype(int)

    # ---- label (events AFTER the first session's calendar day) ----
    m = events[["visitor_id", "ts"]].join(t[["first_seen", "first_end"]], on="visitor_id", how="inner")
    back = (m.ts.dt.normalize() > m.first_end.dt.normalize()) & (m.ts <= m.first_seen + window)
    t[TARGET] = back.groupby(m.visitor_id).any().reindex(t.index).fillna(False).astype(int)
    t["label_known"] = (t.first_seen + window) <= as_of
    return t.drop(columns=["first_referrer", "first_ua", "first_end"]).reset_index()
