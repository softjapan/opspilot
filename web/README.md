# OpsPilot Web UI

Minimal Next.js dashboard for OpsPilot: submit a question, watch the
investigation's progress stream live over SSE, and see the resulting
Findings/Confidence/Recommendation. See the [repo root README](../README.md)
for the full project.

```bash
npm install
npm run dev
```

Requires `opspilot-api` running (see the root README's Quickstart) and
`NEXT_PUBLIC_API_BASE_URL` pointed at it — copy `.env.local.example` to
`.env.local` if you need to override the default (`http://localhost:8000`).
