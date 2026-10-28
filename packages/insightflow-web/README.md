# insightflow-web

Browser SDK for sending InsightFlow analytics events.

## Install

```bash
npm install insightflow-web
```

Or from this repo locally:

```bash
npm install file:../packages/insightflow-web
```

## Usage

```js
import { createInsightFlow } from "insightflow-web";

const insightflow = createInsightFlow({
  apiKey: "YOUR_API_KEY",
  projectId: "YOUR_PROJECT_ID",
  endpoint: "https://your-backend.com/api/ingest/event",
  autoTrackPageViews: false,
  autoTrackClicks: true,
  autoTrackScroll: true,
});

insightflow.page();
insightflow.track("signup_click", { plan: "pro" });
insightflow.identify("user_123");
```

## API

- `track(eventName, properties)`
- `page(properties)`
- `identify(userId, traits)`
- `resetIdentity()`
- `attachAutoTracking({ click, scroll })`
- `start()`
- `stop()`
