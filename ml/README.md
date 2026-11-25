# InsightFlow ML — visitor retention prediction

**Question the model answers:** given a visitor's FIRST session, will they come back on a later
day within 7 days?  (`returned_7d`, defined in `insightflow_ml/config.py` + `features.py`)

```
Mongo events ─► data_sources ─► cleaning ─► features(+label) ─► train ─► artifacts/
 (M1)             (M1)           (M1)         (M2)              (M3)       │
                                                                          ▼
React PredictionsPanel ◄─ Node /api/ml/* ◄─ FastAPI (api.py, predict.py) (M4)  ─► Gemini context (M5)
```

## Run
```bash
cd ml && python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m pytest -q tests                      # 10 tests, incl. leakage tests
python -m insightflow_ml.train --source synthetic
ML_API_KEY=devsecret uvicorn insightflow_ml.api:app --port 8001
```

## Non-negotiable rules (examiners will ask about these)
1. Features come from the first session only; the label comes from later days only (`tests/test_pipeline.py` enforce it).
2. Visitors whose 7-day window is unfinished are never used for training.
3. Train/test split is temporal with a 7-day purge gap. Model selection uses CV on train only, never the test set.
4. Always report the baselines (`baseline_prior`, `baseline_rule_pageviews`). If ML does not beat the rule, say so.
5. Synthetic data proves the pipeline works; it is NOT evidence of model quality. Report results on REAL data
   (your own SDK traffic and/or the public REES46 dataset) and label every number with its `data_source`.
6. `metadata.json` records everything needed to reproduce a result.

## Integration (5 minutes)
- Copy `integration/backend/src/*` into `backend/src/`, then in `app.js`:
  `import mlRoutes from "./routes/ml.routes.js";` and `app.use("/api/ml", mlRoutes);`
- backend `.env`: `ML_API_URL=http://localhost:8001` and `ML_API_KEY=<same secret as ML service>`
- Copy `PredictionsPanel.jsx` to `frontend/src/organizer/components/`; in `OrgAnalytics.jsx` add a tab
  `{ id:"predictions", label:"Predictions", icon:BrainCircuit }` and render
  `{activeTab==="predictions" && <PredictionsPanel projectId={selectedProj._id} />}`
- Gemini: in `ai.controller.js` add `const mlBlock = await buildPredictionContext(projectId);` and append
  `${mlBlock}` after `${context}` in the prompt. Also DELETE the `"predictions"` array from the prompt JSON
  schema: right now Gemini invents "7-day forecasts" with no model behind them.
