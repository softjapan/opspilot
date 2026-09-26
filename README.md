# OpsPilot

**AI-powered production incident investigator. Ask your infrastructure why it is broken.**

> OpsPilot never gives an infrastructure diagnosis without evidence.

![OpsPilot demo](docs/demo.gif)

This is real, verified output — not a curated excerpt — from running the exact command below against `docker compose up`'s demo stack, which intentionally breaks MariaDB, nginx, *and* the host's resource metrics at once, so all three analyzers have something to report in a single run:

```
$ opspilot investigate --target demo -q "Why is /api/search slow?"

✓ Analyzing mysql
✓ Analyzing nginx
✓ Analyzing linux
✓ Generating explanation

Root cause:
  502 response from upstream (nginx analyzer).

Finding #1: Slow query detected (via mysql)
  query_time: 0.00768
  rows_examined: 70000
  sql: SELECT * FROM m_staff WHERE m_staff_mall_id = 5 AND m_staff_pc_disp = 1

Finding #2: Missing index causing full table scan (via mysql)
  table: m_staff
  type: ALL
  key: None

Finding #3: 502 response from upstream (via nginx)
  method: GET
  path: /api/search
  status: 502
  occurrences: 4

Finding #4: Upstream connection failure (via nginx)
  message: connect() failed (111: Connection refused) while connecting to upstream...
  upstream: http://127.0.0.1:9/

Finding #5: High CPU usage (via linux)
  cpu_percent: 96.4

Finding #6: High memory usage (via linux)
  memory_percent: 91.2

Confidence: HIGH

Recommendation:
  Check that the upstream service behind this route is running and reachable from nginx.
```

With the default `mock` LLM provider (no API key needed), "root cause" is picked by a simple, deterministic keyword match between the question and each finding's evidence, not real reasoning — see [Configuring an LLM provider](#configuring-an-llm-provider) for how to get an actual LLM-authored explanation across findings like these.

## What it is

OpsPilot investigates production incidents (slow queries, 5xx errors, resource
exhaustion) the way an engineer would: read the logs, run `EXPLAIN`, check
system resources — then explain the root cause with the evidence attached,
never a guess on its own.

```
Detect → Investigate → Explain → Recommend → (future: Human Approval → Execute)
```

v1 stops at **Recommend**. OpsPilot never executes anything on your
infrastructure — it only reads logs, queries `EXPLAIN`, and reports.

- **Evidence-based**: every conclusion cites a `Finding` (slow log entry, `EXPLAIN` row, HTTP status, resource metric) — never a bare LLM opinion.
- **Read-only, by design**: no remote exec, no SSH, no destructive commands. v1 only reads log files, runs `EXPLAIN`, and reads resource metrics.
- **Redacts before it explains**: evidence is scrubbed for emails, passwords, tokens, and card-number-shaped strings *before* it's sent to an LLM provider (see [`src/opspilot/redact/patterns.py`](src/opspilot/redact/patterns.py)). Local CLI/Web display is unaffected — only the LLM-bound payload is redacted.
- **Works without an API key**: findings are always visible; only the natural-language explanation needs an LLM provider (see [Configuring an LLM provider](#configuring-an-llm-provider)).

## Quickstart

Requires Docker.

```bash
git clone <this-repo>
cd opspilot
docker compose up -d --build
```

This starts an intentionally-broken demo stack — a MariaDB table with a
missing index, an nginx endpoint proxying to a closed port — plus OpsPilot's
own API and Web UI. No production credentials, no external accounts needed.

- Web UI: http://localhost:3000 — type a question, click **Investigate**.
- API docs: http://localhost:8000/docs

Or from the CLI (requires [uv](https://docs.astral.sh/uv/)):

```bash
uv sync
uv run opspilot investigate --target demo -q "Why is /api/search slow?"
```

Tear down with `docker compose down`.

## Architecture

```
                    ┌───────────────┐
                    │    Engineer   │
                    └───────┬───────┘
                            │
                     CLI / Web UI
                            │
                            ▼
                  ┌─────────────────┐
                  │    OpsPilot     │
                  │  investigate()  │
                  └────────┬────────┘
                           │
           ┌───────────────┼────────────────┐
           ▼               ▼                ▼
     nginx logs       MariaDB slow log   Linux resources
     (read-only)      + EXPLAIN          (CPU/Mem/Disk)
           │               │                │
           └───────────────┼────────────────┘
                           ▼
                      redact/
                  (scrub secrets)
                           │
                           ▼
                    LLM provider
              (mock / anthropic / openai)
                           │
                           ▼
                 Evidence-based Report
```

`src/opspilot/investigate.py` is the single orchestrator both the CLI
(`src/opspilot/cli/main.py`) and the API (`src/opspilot/api/main.py`) call —
neither surface duplicates this logic.

## Project layout

```
opspilot/
├── src/opspilot/
│   ├── analyzers/       # mysql.py, nginx.py, linux.py — deterministic, evidence-producing
│   ├── redact/          # scrub secrets before they reach an LLM
│   ├── llm/             # pluggable provider: mock / anthropic / openai
│   ├── investigate.py   # shared orchestrator (analyzers → redact → llm)
│   ├── targets.py       # built-in "demo" target, shared by CLI and API
│   ├── cli/             # `opspilot investigate`
│   └── api/             # FastAPI + Server-Sent Events
├── web/                 # Next.js dashboard (TypeScript, App Router)
├── demo/                # the intentionally-broken demo stack
├── tests/               # pytest — analyzers, redaction, mock provider
├── scripts/smoke.sh     # end-to-end smoke test against the running stack
└── docker-compose.yml
```

## Configuring an LLM provider

By default (`OPSPILOT_LLM_PROVIDER=mock`, no API key needed) findings are
explained with a deterministic, rule-based summary — no network call. To get
a real natural-language explanation, copy `.env.example` to `.env` and set:

```bash
OPSPILOT_LLM_PROVIDER=anthropic   # or: openai
ANTHROPIC_API_KEY=...
OPSPILOT_ANTHROPIC_MODEL=...      # a Claude model id available to your account
```

(or the `OPENAI_*` equivalents). Install the matching extra:
`uv sync --extra anthropic` or `uv sync --extra openai`.

## Development

```bash
uv sync                 # install Python dependencies
uv run pytest           # run the test suite

cd web && npm install   # install the Web UI's dependencies
npm run dev             # Next.js dev server on :3000
```

`scripts/smoke.sh` runs an end-to-end check (CLI + API + SSE) against an
already-running `docker compose up -d` stack.

## Roadmap

v1 (this repo) is deliberately scoped to a single CLI + one demo target +
one minimal Web UI. Splitting analyzers into standalone MCP servers, adding
an Evals benchmark (published only once real numbers exist — never
placeholders), and a full-featured Web UI are tracked as future work; see
`plan.md` for the fuller design rationale.

## License

[MIT](LICENSE)
