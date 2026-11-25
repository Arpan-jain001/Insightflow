"""M1 — Validation, identity resolution, bot filtering, sessionisation."""
from __future__ import annotations

import pandas as pd

from .config import BOT_UA_PATTERN, SESSION_GAP_MIN


def resolve_identity(df: pd.DataFrame) -> pd.DataFrame:
    """visitor_id = userId if this anonymous_id was EVER linked to a login, else anonymous_id.

    The existing dashboard uses (userId || anonymousId) per event, which splits one person
    into two (pre-login anon id + post-login user id) and makes the anon half look like it
    never returned. That would corrupt the retention label, so we link them here.
    """
    df = df.copy()
    df["anonymous_id"] = df["anonymous_id"].fillna("").astype(str)
    df["user_id"] = df["user_id"].fillna("").astype(str)
    linked = (df[(df.user_id != "") & (df.anonymous_id != "")]
              .drop_duplicates("anonymous_id")
              .set_index("anonymous_id")["user_id"])
    mapped = df["anonymous_id"].map(linked).fillna("")
    uid = df["user_id"].where(df["user_id"] != "", mapped)
    df["visitor_id"] = uid.where(uid != "", df["anonymous_id"])
    df["user_id"] = uid
    return df


def prepare_events(raw: pd.DataFrame, gap_min: int = SESSION_GAP_MIN):
    """raw canonical events -> (clean events with session_idx, cleaning report)."""
    report = {"rows_in": int(len(raw))}
    df = raw.copy()
    df["ts"] = pd.to_datetime(df["ts"], utc=True, errors="coerce")
    for c in ("event_name", "page", "referrer", "ua"):
        df[c] = df[c].fillna("").astype(str)
    df["scroll_depth"] = pd.to_numeric(df["scroll_depth"], errors="coerce")

    df = resolve_identity(df)
    n = len(df)
    df = df[df.ts.notna() & (df.visitor_id != "") & (df.event_name != "")]
    report["dropped_invalid"] = n - len(df)

    n = len(df)
    df = df[df.ts <= pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=1)]
    report["dropped_future_ts"] = n - len(df)

    n = len(df)
    df = df[~df.ua.str.contains(BOT_UA_PATTERN, case=False, regex=True)]
    report["dropped_bots"] = n - len(df)

    n = len(df)
    df = df.drop_duplicates(["visitor_id", "event_name", "ts", "page"])
    report["dropped_duplicates"] = n - len(df)

    df = df.sort_values(["visitor_id", "ts"]).reset_index(drop=True)
    gap = df.groupby("visitor_id")["ts"].diff() > pd.Timedelta(minutes=gap_min)
    df["session_idx"] = gap.groupby(df["visitor_id"]).cumsum().astype(int)

    report["rows_out"] = int(len(df))
    report["visitors"] = int(df.visitor_id.nunique())
    return df, report
