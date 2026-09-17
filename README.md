# Reclaim — GPU budget intelligence

**Spend less. Protect the work.** A Track 2 decision workspace that connects a CFO's recovery plan to actual jobs, makes assumptions adjustable, and prices the cost of a bad decision.

Solo project by [@weiyu-t](https://github.com/weiyu-t) for the MantisGrid AI Hackathon 2026.

On the official sample, two investigated pilots yield a base scenario of **16,206.57 GPU-hours / $40,516.43 of capacity value**, with an **8,879.80–24,377.49 GPU-hour** scenario range. That is 2.73% of observed allocation and 13.64% of a sample-equivalent 20% cut. Recovery has not been experimentally established; actual recovery could be zero. Freed capacity does not establish a reduced bill.

## Run the submission

Requires Docker with Compose v2.24 or newer. From this repository root:

```bash
# First time only: download the official data using data/README.md, then:
make prep
make generate
make check-data

# The judged entry point, after data has been generated:
docker compose up
```

Open **http://localhost:3000**. The API is at http://localhost:8000/docs. The dashboard builds automatically on the first run. No API key is required to explore the analysis or retrieve a deterministic MCP evidence briefing.

The generator runs unchanged on the container's native filesystem before copying its results into `data/synthetic/`. This avoids an intermittent official generator crash observed on a Mac shared mount. All five outputs match the official semantic checksums.

For local development, use Python 3.12+ and Node 22+:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-app.txt pytest
uvicorn reclaim.main:app --host 127.0.0.1 --port 8000
# In another terminal:
cd dashboard
npm ci
npm run dev
```

## Optional Featherless explanations

Copy `.env.example` to `.env` and set `FEATHERLESS_API_KEY` locally. Keep the key out of source control and browser code. The default model is `zai-org/GLM-4.7-Flash`, with a bounded fallback to `zai-org/GLM-5.3-Flash`. Restart the API container after changing `.env`:

```bash
docker compose up -d --force-recreate api
```

“Get briefing” retrieves evidence through the real MantisGrid MCP server, then sends a small set of public dataset excerpts and calculated summaries to Featherless. Live explanations are labeled, with model, tool trace, timing, and token usage. Unavailable models or missing keys fall back to a deterministic brief. Responses are cached for ten minutes. Explanations cannot change calculations or take operational action.

Answers must match a four-field JSON structure and cite a retrieved finding ID. The model supplies recommendation and pilot prose; numerical evidence is rendered directly from calculation code. The hardware audit also renders financial downside from code to prevent confusion between a negative net benefit and a negative cost. Other briefings use model-written downside prose. Model prose containing digits is rejected. Prose still needs review against the records; these checks do not prove its correctness. Provider reasoning, request headers and keys never enter the run log. Each model attempt has a 45-second total deadline. Container usage logs live in `/app/out/agent_runs.jsonl`; native runs write `out/agent_runs.jsonl`. Logs are ignored by Git and are not persistent across container replacement.

## Explore

- **Overview:** allocation value by outcome, weekly allocation, investigated opportunity and target gap.
- **Recovery plan:** two ranked actions, owner roles, evidence, pilots, and rollback conditions.
- **Risk lab:** vary recovery, useful work disrupted, operator effort, and how much freed capacity reduces a bill.
- **Node decisions:** compare hardware, workload and unresolved cases; audit the proposed drain recommendation and price a targeted versus five-machine drain.
- **GPU cards:** inspect paired compute/memory measurements and 2,475–4,685 quiet-card hours under explicit evidence thresholds; kept outside recovery totals.
- **Evidence:** drill into jobs, per-GPU records and findings; inspect a shared-array failure across 34 machines.
- **Method:** cohort definitions, overlap handling, sample limits and scenario assumptions.

The price selector recalculates dollars without changing cohorts. “Export claims” downloads the same estimates used by the dashboard.

## Verify and export

With the local environment activated:

```bash
make test
make claims
make validate CLAIMS=claims.json URL=http://localhost:3000
cd dashboard && npm run build
```

The official validator accepts the claims schema. Its confidence warning checks only top-level fields ending in `_confidence`; it does not inspect nested estimate confidence. We intentionally provide no calibrated probability: recovery ranges are declared scenarios, and card ranges vary evidence thresholds. This warning is not a complete statement of how judges score calibration. See [REPORT.md](REPORT.md) for the basis and zero-recovery stress case. Claims cover the two recovery cohorts, three node windows, scheduler-recorded hardware failures, and card exposure. Synthetic-incident claims remain omitted.

## Project map

| Path | Purpose |
|---|---|
| `dashboard/` | React/TypeScript interface and Nginx proxy |
| `reclaim/analysis.py` | Cohort accounting, downside scenarios, claims |
| `reclaim/research.py` | Node/window controls, drain cost, per-card exposure |
| `reclaim/investigator.py` | Bounded MCP retrieval and optional Featherless explanation |
| `reclaim/routes.py` | Dashboard API, preserving official routes |
| `api/`, `mcp_layer/` | Official MantisGrid starter services |
| `tests/` | Accounting, joins, API and provider-failure checks |
| `REPORT.md`, `DEMO.md` | Analysis report and four-minute walkthrough |
| `docs/BRIEF.md`, `docs/` | Original task brief and official guides |

## AI and attribution disclosure

This implementation was generated with OpenAI Codex (GPT-6), including the dashboard, accounting and investigation modules, tests, build integration and documentation. The human participant selected Track 2, provided the repository and provider configuration, and authorized live evidence explanations. Further human review is still needed before submission. The official MantisGrid API, MCP tools, preparation scripts, generator binaries, documentation and schema are inherited and attributed, rather than claimed as original work.

Runtime models: Featherless-hosted GLM-4.7-Flash and GLM-5.3-Flash. Frameworks: FastMCP, FastAPI, React, Vite; no autonomous operational agent or additional agent framework. Model calls write explanations only. Numerical results come from Python over the source tables.

Data: MIT SuperCloud TX-GAIA, HPCA '22, CC BY-NC-ND 4.0. See [ATTRIBUTION.md](ATTRIBUTION.md), [LICENSE](LICENSE), and [data/README.md](data/README.md). Do not commit raw or generated telemetry, `.env`, or local run logs.

Submission instructions are in [docs/submission.md](docs/submission.md). The public repository, team details and presentation are separate submission steps; this workspace does not submit the form automatically.
