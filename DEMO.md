# Reclaim: a plain-language demo

Start with the 30-second version for a budget owner. Use the four-minute walkthrough when presenting to the judges.

Read the quoted paragraphs aloud. The **Click** lines tell you what to do; do not read them aloud. The times are a guide, so pause naturally while changing screens.

The whole story is: **Find a possible saving → check the records → consider the harm → test a small change.**

If a term or number feels unclear, read [DEMO_GUIDE.md](DEMO_GUIDE.md) first. You do not need to explain every feature or read the raw data aloud.

## Before recording

1. Open http://localhost:3000 in a window wide enough to show the navigation labels.
2. Leave the top-right price at **$2.50 per GPU-hour**.
3. Open **Downside costs**, click **Reset**, then return to **Overview**.
4. Try the **Explain the machine recommendation** button on **Machine review** once. This lets you see the explanation before presenting it. Return to Overview.
5. In **Trial planner**, choose **Test CPU-only placement**, **Top 3**, and **Owned equipment**. Any commercial checkboxes should be unchecked for the demo. Draft fields persist in this browser.
6. Have this script beside your screen. Keep your API key and `.env` file out of the recording.

## The 30-second version

**Click:** Stay on **Overview**. Read the recommendation, then point across the three figures and the bill reduction line. The top of this screen contains the whole decision.

> I recommend two small trials: test suitable jobs on CPUs, and warn owners about low-activity GPU sessions.
>
> Across eligible work in this sample, the starting estimate is forty thousand five hundred dollars of GPU time freed. If two percent of jobs are disrupted, rework costs about three thousand five hundred, leaving thirty-seven thousand of value.
>
> Bill savings remain unproven. Test these changes before cutting capacity.

Those figures describe a scenario applied to the eligible work in the historical sample. The small trial would tell us whether the assumptions hold. They are not a prediction of what the trial itself earns.

## Four-minute walkthrough for judges

### 0:00–0:25 — The decision

**Click:** Start on **Overview**. Point across the three large figures and the bill reduction line.

> Reclaim helps a computing budget owner decide what to test, what could go wrong, and whether the bill would actually fall.
>
> These two changes could free GPU time valued at about forty thousand dollars under our assumptions. We have not measured that saving yet. The next step is a limited trial.

### 0:25–1:00 — The evidence

**Click:** **Proposed trials** → **Inspect evidence** under **Test CPU-only placement**. Scroll to **Jobs behind the number**, briefly open a job, then close the evidence panel.

> We found 463 tasks that finished successfully but recorded no GPU computing. We would ask their owners to test repeat runs on CPUs, checking the results and how long the work takes.
>
> Every recommendation connects to source records. The second trial would warn owners about long, quiet GPU sessions before considering any timeout.

### 1:00–1:30 — The cost of mistakes

**Click:** **Downside costs**. Move **Useful jobs disrupted** from **2%** to around **30%**. Pause for the result, then **Reset**.

> An incorrect recommendation can create more work. This calculation includes repeated computing and staff time.
>
> When I increase the share of useful work we interrupt, the result becomes negative: rework costs more than the GPU time we free. The slider is a what-if assumption, not a measured error rate.

### 1:30–2:00 — Check the cause before removing a machine

**Click:** **Machine review**. Show **Machine-specific signal**, then **Shared workload signal**. If time allows, show the cached **Explain the machine recommendation** briefing.

> A failed task does not automatically mean a broken computer. We compare problems concentrated on one machine with related work failing across many machines.
>
> That changes who should investigate first. Taking machines out of service also has a cost. The AI explains retrieved evidence; calculation code supplies the numbers.

If the briefing says **MCP evidence · no model**, say: **“The built-in evidence summary remains available without the AI service.”**

### 2:00–2:20 — Look inside the average

**Click:** **GPU usage** → **Which GPU did the work?** Point to the first job’s one busy GPU and three quiet GPUs.

> This job held four GPUs, but only one recorded computing activity. That makes a smaller allocation worth testing. A quiet GPU may still hold useful data, so these hours stay outside our recovery estimate.

### 2:20–3:35 — A focused, funded trial

**Click:** **Trial planner**. Select **Test CPU-only placement** and **Top 3**. Point to **52.4%**. Scroll to **Path to cash** and switch from **Owned equipment** to **Usage-based billing**. Leave the confirmation boxes unchecked.

> Here is the practical insight: three researcher accounts represent over half the GPU time eligible for the CPU trial. We can start by consulting those owners.
>
> That percentage describes historical work. It does not predict what a small trial earns.
>
> How the company pays matters too. Owned equipment can be reused. A prepaid commitment may need a contract change. Usage-based spending falls only when actual billed resources decrease. These checks identify what finance and operations still need to confirm.

**Click:** Scroll to **Draft for review**. Point to the job limit, spending cap, success criteria and stop conditions. Click **Download trial brief**. Leave the responsible person and review date blank unless you are deliberately entering an example; incomplete briefs are labeled drafts.

> The selected owners carry into a brief with a trial lead, review date, spending cap and stop conditions. These starting limits are editable examples.
>
> The brief gives the budget owner something specific to review. Downloading it does not approve or execute a change.

### 3:35–4:00 — Close

**Click:** Return to **Overview**.

> Reclaim connects the evidence to a small next step: who to consult, how money might be saved, and when to stop if the change causes harm.
>
> I built it with AI coding assistance and MantisGrid’s tools. The original contribution is the decision workflow and the investigations behind it.

## If you lose your place

Return to this sentence: **“We found something worth testing, and we show both the evidence and the risk before recommending a change.”**

You can skip extra job records and the third node case. There is no need to read long machine IDs, source-code column names, or every number on the screen.

## After recording

Use the public repository at https://github.com/weiyu-t/reclaim-gpu. Submit the recording or presentation, your name and student/career status, and the Track 2 project details through the form linked in [the submission instructions](docs/submission.md), before **September 17, 2026, 3:00pm PDT**.

This file is a script. It is not a recording, and the submission form has not been completed.
