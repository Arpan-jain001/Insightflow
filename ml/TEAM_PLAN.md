# Team plan (assumes 5 members + lead). Today: 31 Oct 2026. Hard stop: end of Dec.

**Critical path:** the label needs 7 days after each visit, so real data must start flowing THIS WEEK.
Visitors first seen after ~20 Dec can never be labelled in time.

| Member | Owns | Files | Done when |
|---|---|---|---|
| **M1 Data & Collection** | Real data, cleaning, SDK/ingest fixes | `data_sources.py`, `cleaning.py`, `integration/sdk_and_ingest_fixes.md` | SDK embedded on >=2 real sites (college site, club page, friends' projects) by 5 Nov; >=3000 real visitors by 5 Dec; REES46 downloaded and `adapt_rees46` run; cleaning report documented |
| **M2 Features & Labels** | EDA, feature set, label definition | `features.py`, `config.py`, `tests/` | EDA notebook (distributions, return rate, missing data); 2+ new justified features; label definition frozen by 10 Nov; leakage tests extended |
| **M3 Modelling** | LR / RF / XGBoost comparison | `modeling.py`, `train.py` | Hyper-parameter search (RandomizedSearchCV inside CV); results table + ROC/PR/calibration plots; honest write-up of the baseline comparison and CI overlap |
| **M4 ML Service & Deployment** | FastAPI, Node bridge, deploy | `api.py`, `predict.py`, `integration/backend/*` | Service deployed (Render/Railway/HF Space) with `ML_API_KEY`; Node routes merged; retrain endpoint tested; `/health` monitored |
| **M5 Dashboard, Gemini & Docs** | UI + AI explanations + report | `PredictionsPanel.jsx`, prompt in `ai.controller.js` | Predictions tab merged; Gemini explains model output (no invented numbers); report chapters + PPT; demo script |
| **Lead (you)** | Review PRs, freeze interfaces, integration | — | Weekly integration on `main`; contract below unchanged |

## Interfaces (change only with lead approval)
- Raw event columns: `anonymous_id,user_id,event_name,ts,page,referrer,ua,scroll_depth`
- Visitor table: `visitor_id, first_seen, <FEATURE_COLUMNS>, returned_7d, label_known`
- API: `POST /predict/project {projectId}` -> see `predict.summarize()` for the JSON shape

## Schedule
- **1–5 Nov** M1 embeds SDK + applies fixes; everyone runs `pytest`; M4 sets up deploy skeleton
- **5–10 Nov** M2 EDA on synthetic+REES46; label/feature freeze
- **10–24 Nov** M3 tuning/evaluation on REES46 (real) and real collected data when enough; M4 integration
- **20 Nov–5 Dec** M5 UI + Gemini; M1 keeps collecting; final retrain on real data
- **5–15 Dec** testing, bug fixing, load test ingest
- **15–28 Dec** report, PPT, demo rehearsal

## Git workflow
Branches `ml/m1-data`, `ml/m2-features`, `ml/m3-models`, `ml/m4-service`, `ml/m5-dashboard`; PR into `main`,
lead reviews; CI = `pytest -q` must pass. Never commit `.env`, datasets or `*.joblib`.
