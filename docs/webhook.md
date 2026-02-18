# OpenClaw Webhooks

OpenClaw supports sending **webhook callbacks** when scheduled work completes.

The most common pattern is: create a `cron` job → run work in an **isolated** session → deliver the finished run event to your system (n8n/Zapier/self-hosted API) via an HTTP **POST**.

> Note: Webhook payload fields can evolve across versions. Treat the event body as an opaque JSON blob unless you control both ends.

---

## 1) Cron delivery webhooks (recommended)

When creating a cron job, set:

- `delivery.mode: "webhook"`
- `delivery.to: "https://…"` (your HTTPS endpoint)

### Example job

```json
{
  "name": "daily-summary",
  "schedule": { "kind": "cron", "expr": "0 9 * * *", "tz": "America/New_York" },
  "payload": {
    "kind": "agentTurn",
    "message": "Summarize today's priorities.",
    "timeoutSeconds": 120
  },
  "delivery": {
    "mode": "webhook",
    "to": "https://example.com/openclaw/webhook"
  },
  "sessionTarget": "isolated",
  "enabled": true
}
```

### Session target constraints

- `sessionTarget: "main"` **requires** `payload.kind: "systemEvent"`
- `sessionTarget: "isolated"` **requires** `payload.kind: "agentTurn"`

In practice, webhook deliveries are most useful with `isolated + agentTurn`.

---

## 2) What the webhook receives

Your endpoint will receive a POST with a JSON body representing the finished cron run (e.g., job id, run id, status, timestamps, and output/summary/error).

Because schemas may change, design your receiver to:

- log the full JSON for troubleshooting
- extract only the fields you truly need
- be **idempotent** (the same run may be delivered more than once)

---

## 3) Security & reliability

**Strongly recommended**:

- Use **HTTPS** only.
- Add authentication, e.g.:
  - a secret token in the URL (`?token=…`) or
  - a header check (preferred, if supported by your receiver)
- Implement replay protection:
  - store processed `(jobId, runId)` pairs
  - discard duplicates
- Return fast (e.g., 200 OK) and do heavier work asynchronously.

---

## 4) Minimal receiver example (Node/Express)

```js
import express from "express";

const app = express();
app.use(express.json({ limit: "2mb" }));

app.post("/openclaw/webhook", (req, res) => {
  // TODO: verify auth token / signature
  console.log("OpenClaw cron event:", JSON.stringify(req.body));
  res.sendStatus(200);
});

app.listen(3000, () => console.log("listening on :3000"));
```

---

## 5) Troubleshooting checklist

- Can the OpenClaw gateway reach your URL from its network?
- Is your endpoint returning 2xx quickly?
- Are you logging raw payloads to debug schema expectations?
- Are you deduplicating events (idempotency)?
