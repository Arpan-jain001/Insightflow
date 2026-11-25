"""How much usable data do I have?   python -m insightflow_ml.check_data --project-id <id>"""
import argparse
import os

import pandas as pd

from . import config as C
from .cleaning import prepare_events
from .data_sources import load_from_csv, load_from_mongo
from .features import build_visitor_table


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-id"); ap.add_argument("--csv")
    a = ap.parse_args()
    raw = load_from_csv(a.csv) if a.csv else load_from_mongo(
        os.environ["MONGO_URI"], a.project_id, db_name=os.getenv("MONGO_DB") or None)
    if raw.empty:
        print("No events found for this project. Check project id / MONGO_URI / MONGO_DB."); return
    ev, rep = prepare_events(raw)
    vt = build_visitor_table(ev)
    known = vt[vt.label_known]
    now = pd.Timestamp.now(tz="UTC")
    print(f"Events (after cleaning): {len(ev)}   (bots removed: {rep['dropped_bots']}, duplicates: {rep['dropped_duplicates']})")
    print(f"Unique visitors:         {len(vt)}")
    print(f"First event: {ev.ts.min():%d %b %Y %H:%M}   Last event: {ev.ts.max():%d %b %Y %H:%M}")
    print(f"Visitors with 7-day outcome known (usable for training): {len(known)}")
    if len(known):
        print(f"  of those, came back within 7 days: {int(known[C.TARGET].sum())} ({known[C.TARGET].mean():.0%})")
    print(f"Visitors still waiting for their 7 days (scored live only): {len(vt) - len(known)}")
    print()
    need = C.MIN_TRAIN_ROWS
    if len(known) >= need and known[C.TARGET].nunique() == 2 and known[C.TARGET].sum() >= 30:
        print(f"READY: you can train on real data now.")
    else:
        short = max(need - len(known), 0)
        print(f"NOT READY: need >= {need} usable visitors and >= 30 who came back; you have {len(known)}"
              f" (about {short} more).")
        print("Visitors become usable 7 days after their first visit, so data collected today is usable on "
              f"{(now + pd.Timedelta(days=C.LABEL_WINDOW_DAYS)):%d %b}.")


if __name__ == "__main__":
    main()