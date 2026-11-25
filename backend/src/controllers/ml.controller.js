// backend/src/controllers/ml.controller.js  (NEW)
import { getAccessibleProject } from "../services/projectAccess.service.js";
import { getProjectPrediction, getModelInfo } from "../services/ml.service.js";

export const predictionsCtrl = async (req, res, next) => {
  try {
    await getAccessibleProject({ projectId: req.query.projectId, user: req.user });
    const data = await getProjectPrediction(req.query.projectId, { force: req.query.refresh === "1" });
    res.json({ success: true, data });
  } catch (e) { next(e); }
};

export const modelInfoCtrl = async (req, res, next) => {
  try {
    const data = await getModelInfo();
    res.json({ success: true, data });
  } catch (e) { next(e); }
};
