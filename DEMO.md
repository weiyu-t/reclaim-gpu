# Four-minute demo

Before recording: run `docker compose up`, open http://localhost:3000, select $2.50/GPU-hour and reset the Risk lab. Warm the hardware MCP briefing once so its trace is ready. Keep `.env` and credentials out of the recording. The live model is optional; call the deterministic fallback what it is if the provider is unavailable.

**0:00–0:35 — The decision.** Open Overview. “The CFO needs a 20% cut without slowing research. Reclaim starts with two investigated pilots worth about $40,500 of capacity in the base scenario. That covers only 13.6% of the target. The rest still needs evidence.” Show the range, target gap and numeric downside. “At 2% disruption, rework costs about $3,450. We assume zero bill reduction.”

**0:35–1:10 — Follow the money to a job.** Open Recovery plan → CPU placement → Inspect evidence. “These 463 successful jobs recorded no GPU compute. Research platform owns an opt-in placement pilot. Every action has a filter, duration cap, owner, pilot and rollback.” Click one job. “The other pilot warns about long low-activity interactive sessions. We remove 109 overlaps so every job is counted once.” Close the drawer.

**1:10–2:15 — Challenge the proposed API.** Open Node decisions. “The proposed API says drain five machines for $57,000. Its finding-count ranking misses the explicit hardware episode.” Show the hardware controls: “114 matching failures here, none in 311 same-window jobs elsewhere for the same researchers.” Click Shared workload: “Here, 568 siblings fail elsewhere with the same exit code. Start with the workload.” Click Cause unresolved: “A past fault does not permanently label a machine.” Scroll to drain cost: “Even the hardware episode loses only 0.022 GPU-hours because jobs fail immediately. Inspection can matter for research reliability, but the GPU-time savings do not pay for this drain.” Toggle one to five machines. Show the MCP hardware briefing and tool trace; numbers are computed by code.

**2:15–2:55 — An average hides the card.** Open GPU cards. “We investigated 4,100 quiet-card hours, with a 2,475–4,685 range across evidence thresholds.” Show the largest job: its average masks one busy GPU and three quiet ones. Click another job with memory on a zero-compute card. “Zero compute can still hold useful memory or transfers. We keep this exposure out of the savings headline until a fewer-card replay preserves output and runtime.”

**2:55–3:30 — What if we are wrong?** Open Risk lab. Raise disruption to 30% and show negative net value. Set recovery to zero. “The assumptions are visible and can make the recommendation lose money. Before scaling, measure false positives, output parity, released hours and queue delay.” Reset.

**3:30–4:00 — Reproduce it.** Open Method and Export claims. “The dashboard and claims share deterministic calculations. We expose raw records, three defensible node decisions, scheduler retry history and explicit thresholds. Docker starts everything unattended, all five official checksums match, and no API key is required. The recommendation is a measured pilot with owners and rollback, followed by evidence before expansion.”

## Submission handoff

- Review `REPORT.md` and `claims.json` against the running dashboard.
- Use the public repository's default branch at its latest pushed commit.
- Record the actual running demo, approximately four minutes, following the sequence above.
- Supply your name and student/career status in the form.
- Submit Track 2, the project description, repository and presentation through the form linked in `docs/submission.md` before September 17, 2026, 3:00pm PDT.

This script is not a recording. The workspace does not submit the form automatically.
