# Data-quality fixes (these affect ML label/feature quality) — owner: M1

1. SDK `packages/insightflow-web/src/index.js` fires `scroll_depth` on EVERY scroll event.
   One reader can send hundreds of events and burn the whole project's ingest limit.
   Replace the onScroll body with milestone tracking:
   ```js
   const seen = new Set();
   const onScroll = () => {
     const total = Math.max(document.documentElement.scrollHeight - window.innerHeight, 1);
     const depth = Math.round((window.scrollY / total) * 100);
     for (const m of [25, 50, 75, 100]) {
       const key = `${getLocationKey()}:${m}`;
       if (depth >= m && !seen.has(key)) { seen.add(key); track("scroll_depth", { scrollDepth: m }); }
     }
   };
   ```
2. `backend/src/routes/ingest.routes.js`: `checkRateLimit(apiKey)` allows 100 events/min for the
   WHOLE project (all visitors together), in memory, per server instance. Under real traffic events
   are silently dropped with 429 -> sessions look shorter than they are -> biased features.
   Key it by `apiKey + ":" + (anonymousId || req.ip)` and raise the limit (or use a token bucket).
3. SDK has no `page_leave`/duration event. Duration is currently derived from timestamps of the
   first and last event, so a one-page visit always has duration 0. Add a `visibilitychange`/
   `pagehide` handler that sends `page_leave` via `navigator.sendBeacon` (needs the API key in the
   body or a query param, because sendBeacon cannot set `x-api-key`).
