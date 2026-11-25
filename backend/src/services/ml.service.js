// backend/src/services/ml.service.js  (NEW) — talks to the Python ML service
import axios from "axios";

const CACHE_MS = 10 * 60 * 1000;
const cache = new Map(); // projectId -> { at, data }

// Read env at CALL time (not import time): .env may be loaded after this module is imported.
const client = () =>
  axios.create({
    baseURL: process.env.ML_API_URL || "http://localhost:8001",
    timeout: 30000,
    headers: { "x-ml-key": process.env.ML_API_KEY || "" },
  });

const wrap = (e) => {
  console.error("[ML]", e.response?.status || e.code, JSON.stringify(e.response?.data || e.message));
  const err = new Error(
    e.response?.status === 409
      ? "Prediction model is not trained yet."
      : "Prediction service is unavailable."
  );
  err.statusCode = e.response?.status === 409 ? 409 : 502;
  return err;
};

export const getProjectPrediction = async (projectId, { force = false } = {}) => {
  const hit = cache.get(String(projectId));
  if (!force && hit && Date.now() - hit.at < CACHE_MS) return hit.data;
  try {
    const { data } = await client().post("/predict/project", { projectId: String(projectId) });
    cache.set(String(projectId), { at: Date.now(), data });
    return data;
  } catch (e) {
    throw wrap(e);
  }
};

export const getModelInfo = async () => {
  try {
    return (await client().get("/model")).data;
  } catch (e) {
    throw wrap(e);
  }
};

// Text block appended to the Gemini prompt context (see README step 4).
// Gemini must EXPLAIN these numbers, never invent its own forecasts.
export const buildPredictionContext = async (projectId) => {
  try {
    const p = await getProjectPrediction(projectId);
    if (p.status !== "ok") return "\nML RETENTION MODEL: not enough recent visitors to score.\n";
    const drivers = p.top_drivers.map((d) => `${d.feature} (${d.importance.toFixed(3)})`).join(", ");
    return `
ML RETENTION MODEL OUTPUT (use ONLY these numbers for any prediction; do not invent forecasts):
  - Model: ${p.model.name}, trained on ${p.model.trained_on}${p.model.is_synthetic ? " (SYNTHETIC DATA - say predictions are illustrative)" : ""}, test ROC-AUC ${p.model.test_roc_auc.toFixed(2)}
  - Recent visitors scored: ${p.counts.pending_scored}; average probability of returning within 7 days: ${(p.avg_return_probability * 100).toFixed(0)}%
  - Likelihood buckets: low ${p.buckets.low}, medium ${p.buckets.medium}, high ${p.buckets.high}
  - Observed 7-day return rate (older visitors): ${p.observed_return_rate_7d ?? "n/a"}
  - Most influential behaviours: ${drivers}
`;
  } catch {
    return "";
  }
};