# Demo guide (InsightFlow + ML)

## Run order (3 terminals)
1. ML service: `cd ml` -> edit `start_ml.bat` (MONGO_URI, key) -> run it. Check http://localhost:8001/health shows `"model_loaded": true`
2. Backend: add `ML_API_URL=http://localhost:8001` and `ML_API_KEY=<same key>` to `backend/.env`, then `npm run dev`
3. Frontend: `npm run dev` -> open a project -> **Predictions** tab

## If the tab is empty / errors
- "Not enough recent visitors": the model scores only visitors first seen in the last 7 days. Re-run **Generate demo data** or send fresh events via the SDK.
- "Prediction service is unavailable": ML service is not running, or ML_API_KEY differs between backend and ML service.
- "Model is not trained yet": run `cd ml` then `python -m insightflow_ml.train --source synthetic`.

## What to say honestly in the presentation
- The pre-trained model is trained on SYNTHETIC data (the yellow banner on the tab says so). Say: "the pipeline works end to end; real data is being collected; final accuracy will be reported on real data."
- Do not call synthetic/demo-data numbers "model accuracy".
- Model comparison table: `ml/artifacts/metadata.json`, or run `python -m insightflow_ml.train --source synthetic` live (~1 min).

## 30-second explanation
Raw events -> cleaning -> features from the first session -> label "returned within 7 days?" -> Logistic Regression / Random Forest / XGBoost compared -> best model served by FastAPI -> shown on the dashboard and explained by Gemini.
