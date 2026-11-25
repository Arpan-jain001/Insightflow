// frontend/src/organizer/components/PredictionsPanel.jsx  (NEW)
// Usage inside OrgAnalytics.jsx:  {activeTab === "predictions" && <PredictionsPanel projectId={selectedProj._id} />}
import { useEffect, useState, useCallback } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { AlertTriangle, RefreshCw, BrainCircuit } from "lucide-react";

const BASE = import.meta.env.VITE_BACKEND_API_URL;
const hdr = () => ({ Authorization: `Bearer ${localStorage.getItem("accessToken")}` });
const BUCKET_COLORS = { low: "#f43f8e", medium: "#f59e0b", high: "#10d990" };

const PredictionsPanel = ({ projectId }) => {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const load = useCallback(async (refresh = false) => {
    if (!projectId) return;
    setLoading(true); setErr("");
    try {
      const res = await fetch(`${BASE}/api/ml/predictions?projectId=${projectId}${refresh ? "&refresh=1" : ""}`, { headers: hdr() });
      const json = await res.json();
      if (json.success) setData(json.data); else setErr(json.message || "Predictions unavailable");
    } catch { setErr("Failed to reach prediction service"); }
    finally { setLoading(false); }
  }, [projectId]);

  useEffect(() => { load(); }, [load]);

  if (err) return <div className="p-4 text-sm text-[#f43f8e]">{err}</div>;
  if (!data) return <div className="p-4 text-sm text-[#8aa4c0]">{loading ? "Scoring visitors..." : "No data"}</div>;

  const buckets = data.buckets ? Object.entries(data.buckets).map(([k, v]) => ({ name: k, visitors: v })) : [];
  const drivers = (data.top_drivers || []).map((d) => ({ name: d.feature, value: Math.max(0, d.importance) }));

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h2 className="text-lg font-black text-[#e8f4ff] flex items-center gap-2"><BrainCircuit size={18} /> Retention Prediction</h2>
        <button onClick={() => load(true)} className="text-xs text-[#00e5ff] flex items-center gap-1"><RefreshCw size={12} /> Refresh</button>
      </div>

      {data.model.is_synthetic && (
        <div className="flex gap-2 p-3 rounded border border-[#f59e0b]/40 text-xs text-[#f59e0b]">
          <AlertTriangle size={14} /> Model was trained on synthetic data. Predictions are illustrative only.
        </div>
      )}
      {!data.model.beats_baseline && (
        <div className="p-3 rounded border border-[#f59e0b]/40 text-xs text-[#f59e0b]">
          This model does not beat a simple "more page views = more likely to return" rule. Treat as low confidence.
        </div>
      )}

      {data.status !== "ok" ? (
        <p className="text-sm text-[#8aa4c0]">Not enough recent visitors to score yet.</p>
      ) : (
        <>
          {data.counts.pending_scored < 30 && (
            <p className="text-xs text-[#f59e0b]">Only {data.counts.pending_scored} recent visitors scored. Averages on so few visitors are not reliable; more traffic gives a meaningful result.</p>
          )}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-[#e8f4ff]">
            <Stat label="Recent visitors scored" value={data.counts.pending_scored} />
            <Stat label="Avg. chance of returning (7d)" value={`${Math.round(data.avg_return_probability * 100)}%`} />
            <Stat label="Observed return rate (older)" value={data.observed_return_rate_7d == null ? "n/a" : `${Math.round(data.observed_return_rate_7d * 100)}%`} />
            <Stat label="Model test AUC" value={data.model.test_roc_auc.toFixed(2)} />
          </div>

          <div className="grid md:grid-cols-2 gap-5">
            <Card title="Return likelihood">
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={buckets}><XAxis dataKey="name" stroke="#8aa4c0" /><YAxis stroke="#8aa4c0" /><Tooltip contentStyle={{ background:"#0a1224", border:"1px solid #1a2a4a", borderRadius:6, color:"#e8f4ff", fontSize:12 }} labelStyle={{ color:"#e8f4ff" }} itemStyle={{ color:"#e8f4ff" }} cursor={{ fill:"rgba(255,255,255,0.05)" }} formatter={(v) => (typeof v === "number" ? Number(v.toFixed(4)) : v)} />
                  <Bar dataKey="visitors">{buckets.map((b) => <Cell key={b.name} fill={BUCKET_COLORS[b.name]} />)}</Bar>
                </BarChart>
              </ResponsiveContainer>
            </Card>
            <Card title="What drives retention (permutation importance)">
              <ResponsiveContainer width="100%" height={230}>
                <BarChart data={drivers} layout="vertical" margin={{ left: 10, right: 10 }}><XAxis type="number" stroke="#8aa4c0" /><YAxis type="category" dataKey="name" width={150} interval={0} tick={{ fontSize: 11 }} stroke="#8aa4c0" /><Tooltip contentStyle={{ background:"#0a1224", border:"1px solid #1a2a4a", borderRadius:6, color:"#e8f4ff", fontSize:12 }} labelStyle={{ color:"#e8f4ff" }} itemStyle={{ color:"#e8f4ff" }} cursor={{ fill:"rgba(255,255,255,0.05)" }} formatter={(v) => (typeof v === "number" ? Number(v.toFixed(4)) : v)} />
                  <Bar dataKey="value" fill="#a855f7" />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          </div>

          <Card title="Segments (recent visitors)">
            {!(data.segments?.referrer_type || []).length && (
              <p className="text-xs text-[#8aa4c0]">Needs at least 5 recent visitors per traffic source to show segments.</p>
            )}
            {(data.segments?.referrer_type || []).map((s) => (
              <div key={s.segment} className="flex justify-between text-xs py-1 text-[#e8f4ff]">
                <span>{s.segment} ({s.visitors})</span><span>{Math.round(s.avg_return_probability * 100)}%</span>
              </div>
            ))}
          </Card>
        </>
      )}
      <p className="text-[10px] text-[#8aa4c0]">
        {data.model.name} trained on {data.model.trained_on}. Label: {data.model.label}.
      </p>
    </div>
  );
};

const Stat = ({ label, value }) => (
  <div className="p-3 rounded border border-white/10"><p className="text-[10px] text-[#8aa4c0]">{label}</p><p className="text-xl font-black">{value}</p></div>
);
const Card = ({ title, children }) => (
  <div className="p-4 rounded border border-white/10"><p className="text-xs text-[#8aa4c0] mb-2">{title}</p>{children}</div>
);

export default PredictionsPanel;