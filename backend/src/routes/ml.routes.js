// backend/src/routes/ml.routes.js  (NEW)
import express from "express";
import { protect } from "../middleware/auth.middleware.js";
import { predictionsCtrl, modelInfoCtrl } from "../controllers/ml.controller.js";

const router = express.Router();
router.get("/predictions", protect, predictionsCtrl);
router.get("/model", protect, modelInfoCtrl);
export default router;
