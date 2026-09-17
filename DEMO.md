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
5. Have this script beside your screen. Keep your API key and `.env` file out of the recording.

## The 30-second version

**Click:** Stay on **Overview**. Read the recommendation, then point across the three figures and the bill reduction line. The top of this screen contains the whole decision.

> I recommend two small trials: test suitable jobs on CPUs, and warn owners about low-activity GPU sessions.
>
> Across eligible work in this sample, the starting estimate is forty thousand five hundred dollars of GPU time freed. If two percent of jobs are disrupted, rework costs about three thousand five hundred, leaving thirty-seven thousand of value.
>
> Bill savings remain unproven. Test these changes before cutting capacity.

Those figures describe a scenario applied to the eligible work in the historical sample. The small trial would tell us whether the assumptions hold. They are not a prediction of what the trial itself earns.

## Four-minute walkthrough for judges

### 0:00–0:35 — What does this help someone do?

**Click:** Start on **Overview**. Point to **$40.5K** under **Potential value of GPU time freed**.

> This is Reclaim. It helps someone responsible for the computing budget decide where to reduce waste without interrupting useful work.
>
> We examined records from 225 machines and found two changes worth testing. Under our starting assumptions, they could free GPU time valued at around forty thousand dollars.
>
> That means computing time we could reuse. It does not mean the company has already saved that money.

### 0:35–1:20 — What would we actually change?

**Click:** **Proposed trials** → **Inspect evidence** under **Test CPU-only placement**. Scroll to **Jobs behind the number** and click one job ID. Briefly show the record, then close the large evidence panel using its top-right X.

> The first idea comes from 463 tasks that finished successfully but recorded no GPU computing activity. We would test whether those tasks can run on a regular CPU instead, leaving the GPU available for work that needs it.
>
> We can open the actual records behind that suggestion. We would check that the results stay correct and the work does not become slower before changing the default.
>
> The second idea is to warn researchers about long GPU sessions with very little activity. We start with a warning because quiet work might still be useful.

### 1:20–2:00 — What if our advice is wrong?

**Click:** **Downside costs**. Point to the result on the right. Move **Useful jobs disrupted** from **2%** to approximately **30%**. Then click **Reset**.

> A cost-cutting suggestion can create more work if it interrupts something useful.
>
> This screen asks what happens if we get it wrong. It counts the computing work that would have to be repeated and the staff time needed to respond.
>
> When I increase the share of useful jobs we accidentally interrupt, the result becomes negative. The cost of rework is now larger than the value of the computing time we free.
>
> This is a what-if test, not a prediction.

### 2:00–2:55 — Is the machine really the problem?

**Click:** **Machine review**. Start with **Machine-specific signal**, then select **Shared workload signal**. Scroll to **What does taking capacity away cost?** and switch from **One targeted machine** to **Five machines**. Return to **One targeted machine**.

> A failed task does not automatically mean a broken machine.
>
> In the first example, the same error keeps appearing on one machine but not in the comparison jobs elsewhere. That machine deserves inspection.
>
> In the second example, related tasks fail on many machines. We should investigate the shared work before blaming the computers.
>
> Taking a machine out of service also removes computing time. This calculator shows that cost, including staff effort. Taking five machines out costs more than taking one out.

**Click:** Scroll down to **Explain the machine recommendation**. Click it and show the resulting briefing. You do not need to read it aloud.

> The AI can explain the retrieved evidence. The numbers and this financial comparison come from calculation code.

If the result says **MCP evidence · no model**, replace that last paragraph with:

> The AI service is unavailable, so this is the built-in evidence summary. The calculations still work.

### 2:55–3:30 — What does an average hide?

**Click:** **GPU usage**. Scroll to **Which GPU did the work?** Leave the first job selected. Point to its four GPU rows: one shows **99%** average compute, and three show **0%**.

> Here, one task held four GPUs. One did almost all the computing, while three recorded none.
>
> Looking only at the task’s average would hide that difference. This is a reason to test whether it can use fewer GPUs.
>
> But a quiet GPU might still hold useful data. We keep these hours separate from our estimated savings until we test the change and check the results.

### 3:30–4:00 — What is the recommendation?

**Click:** Return to **Overview**. Point to **Export claims**; you can click it to download the numbers.

> Reclaim’s recommendation is to start with a small test, check the results with the people doing the work, and expand only when the evidence supports it.
>
> I built this with AI coding assistance and MantisGrid’s data tools. The dashboard links recommendations to records, shows the cost of mistakes, and exports its calculations for review.
>
> It helps the budget owner make a decision they can explain.

## If you lose your place

Return to this sentence: **“We found something worth testing, and we show both the evidence and the risk before recommending a change.”**

You can skip extra job records and the third node case. There is no need to read long machine IDs, source-code column names, or every number on the screen.

## After recording

Use the public repository at https://github.com/weiyu-t/reclaim-gpu. Submit the recording or presentation, your name and student/career status, and the Track 2 project details through the form linked in [the submission instructions](docs/submission.md), before **September 17, 2026, 3:00pm PDT**.

This file is a script. It is not a recording, and the submission form has not been completed.
