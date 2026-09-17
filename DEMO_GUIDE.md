# Understand Reclaim before presenting it

Reclaim helps answer three questions: **Where might we free up computing time? What evidence supports that idea? What could we lose if the idea is wrong?**

Think of a research lab with expensive equipment. Some equipment is booked but barely used. That is a reason to investigate the booking. It does not prove that cancelling it would be safe, or that the lab would get its money back.

That is the decision our dashboard helps someone make.

## The few terms you need

| On the screen | What it means |
|---|---|
| GPU | A specialized processor used for heavy parallel calculations. It is a resource researchers book for their work. |
| CPU | A computer’s general-purpose processor. We want to test whether some tasks can use this without also booking a GPU. |
| Job or task | One piece of computing work submitted by a researcher. |
| Node | One machine. The machines in this dataset each have two GPUs. |
| GPU-hour | One GPU held for one hour. Four GPUs held for two hours equals eight GPU-hours. It measures time allocated, not how much useful computation happened. |
| Capacity | Computing resources available to do work. Freeing capacity can let other work run. |
| Capacity value | Freed GPU-hours multiplied by a reference hourly price. It is a way to compare time and costs; it is not proof of a smaller bill. |
| Drain | Stop assigning new work to a machine and take it out of service in a controlled way, usually for inspection or repair. |
| Scenario / what-if | A calculation based on assumptions we choose. It tells us what follows **if** those assumptions hold. |
| Pilot | A small, monitored trial before making a wider change. |
| MCP | The connection the explanation workflow uses to retrieve evidence from MantisGrid’s tools. You can simply say “the tools that fetch the evidence.” |

## What the headline actually means

The headline is approximately **$40,500 of potential computing-time value**. We have not actually changed anyone’s jobs or measured the resulting savings.

The starting calculation has two parts:

| Proposed trial | What we observed | What we assume for the starting estimate |
|---|---|---|
| Try CPU-only runs | 463 completed tasks with no recorded GPU compute; about 12,000 eligible GPU-hours | About 75% of those eligible hours could be freed after moving suitable work to CPUs. |
| Warn about long, quiet sessions | 797 other tasks with long interactive bookings and little recorded GPU activity; about 28,900 eligible hours after allowing four hours per GPU | About 25% of those eligible hours could be freed. |

Together, the assumptions give about **16,200 GPU-hours**. At **$2.50 per GPU-hour**, that is roughly **$40,500**.

The records and eligibility rules are checked by code. **The 75% and 25% recovery assumptions have not been proven by an experiment.** They are why the next step is a trial. Actual recovery might be zero.

Some tasks matched both ideas. We counted those tasks only in the first group, so we did not claim their hours twice.

The lower and higher headline values come from choosing more cautious or more optimistic recovery assumptions. They are not a promise that the result must fall within that range.

## Why freed time is different from money saved

If the lab already owns its equipment, freeing a booking makes the equipment available. It does not refund the purchase price.

The same applies here. We might help other jobs run sooner or reduce the need for future purchases. To claim an actual bill reduction, someone must also be able to reduce a paid reservation, rental, purchase, or other real expense. We have not established that, so the dashboard starts with **$0 bill reduction**.

The 20% target is also a comparison against the value of the observed sample. We do not claim we have achieved a real company’s next-quarter budget cut.

## Why the Downside costs can turn negative

Imagine that a job looks quiet, but it is preparing data that the researcher still needs. Interrupting it could mean repeating work and asking an operator to help.

The starting scenario assumes that **2% of the selected jobs** are disrupted, each repeats its observed GPU time, and each needs half an hour of operator help. That adds up to about **$3,450 in valued rework**, using the reference GPU rate and $95 per staff hour.

The estimated benefit is about $40,500. Subtract the rework and about **$37,100** remains in computing-time value. This still is not cash savings.

When you move the disruption slider to 30%, the modeled rework costs more than the estimated benefit. **Thirty percent is a stress test you chose, not a measured error rate.**

The model also does not price every consequence, such as a delayed paper or a missed research deadline. Those need discussion with the people doing the work.

## What the node examples teach us

A machine can host a failed job without causing the failure.

- **Machine-specific example:** Three researchers have 114 jobs with the same failure signature on one machine. For those researchers, none of 311 comparison jobs elsewhere in the same period has that signature. This makes the machine worth investigating. It does not prove a particular physical part is broken, and the comparison jobs need not be identical experiments.
- **Shared-work example:** Related tasks show the same failure across many machines. The shared work or its software environment is the narrower place to start investigating.
- **Unresolved example:** The evidence does not establish the cause. We say that instead of automatically blaming the machine.

You do not need to memorize the machine names. The useful distinction is **“does the problem stay with one machine, or follow the work across machines?”**

## Why the drain calculator can show a loss even for a suspicious machine

The matching failures in our hardware example happen almost immediately, within zero to five seconds. Their measured GPU time is very small.

Taking a machine out for hours and paying for inspection can therefore cost more than the GPU time those particular failures consumed. The default calculation values unavailable capacity plus staff effort at **$115**, versus about **three cents** of assumed avoided GPU time.

That does **not** mean inspection is pointless. Researchers may lose progress or spend time debugging; the calculator has no reliable price for that. It means we cannot justify a broad shutdown simply by claiming large GPU-hour savings from these short failures.

Switching from one machine to five changes the amount of capacity taken out of service. It does not prove those five machines should be inspected, or reproduce the proposed API’s exact selection.

## What the GPU-card screen adds

A task can book more than one GPU. Its average can conceal very different behavior on each one.

The first example booked four GPUs. One averaged 99% compute activity; the other three recorded zero compute activity. Averaging those four values gives 24.75%, which hides where the work actually happened.

We found about **4,100 GPU-hours on cards with zero average and peak compute** in completed, single-attempt tasks that also had a busier card. This is time worth investigating, not proven removable time.

A quiet card can still hold useful data in memory. The memory chart shows peak occupancy. Transfer counters are rough measurements and cannot prove the card was doing useful work. The next step is a fewer-GPU trial that checks both the answer and how long it takes.

**These 4,100 hours are not included in the $40,500 headline.**

## What the Trial planner adds

The first decision is who to speak with. For the CPU idea, three researcher accounts account for **52.4% of eligible GPU time**, across 63 historical jobs. This is why we can start with a focused conversation. It does not mean three people are wasting resources, or that a five-job trial will recover half the total.

The payment choice explains how resource use connects to the budget. Owned equipment can be reused; prepaid capacity may require a contract change; usage-based spending falls only when actual billed resources decrease. The checkboxes record what finance and operations tell us. They do not turn an estimate into verified savings.

The draft brief asks for a trial lead and review date, plus proposed limits. The starting five jobs, seven days, $500 and 10% maximum runtime increase are examples for the owner to edit. The software does not enforce those limits or authorize changes. Download the brief, open it in a browser and print if needed. It stays a draft until someone reviews it.

A useful sentence is: **“We found a concentrated opportunity, then made the next step small enough to review, fund and stop.”**

## What the AI does—and what we built

The supplied MantisGrid tools provide findings, rules, and relationships between records. Reclaim adds the dashboard, its own calculations and investigations, and the cost-of-mistakes models.

The optional Featherless model writes a short explanation of evidence retrieved through MCP. It does not run the cluster or decide to shut down machines. Code supplies the numerical evidence and the hardware briefing’s financial downside. Model-written advice can still be wrong and should be checked against the records.

If the model service is unavailable, the app shows a built-in summary based on the same evidence. That is why the judges can use the dashboard without an API key.

AI coding assistance helped build the application and analysis. That assistance and the inherited starter code are disclosed in the README. A truthful way to describe your role is: **“I built this with AI coding assistance, and I’m presenting the decision workflow and its limitations.”**

## Short answers if someone asks

| Question | A plain answer |
|---|---|
| Have you saved $40,500? | “No. That is the value of time we might free under stated assumptions. We need to test the changes.” |
| Why not cut all the apparently wasted time? | “Low activity and cancelled work are clues, not proof that the time can safely be removed.” |
| What would you do first? | “Ask owners of the completed zero-GPU-compute jobs to try a small set on CPUs, then compare correctness and runtime.” |
| What is different from just showing alerts? | “We connect an alert to source records, a proposed action, and the cost of getting that action wrong.” |
| Are the numbers made up by the model? | “No. The records feed calculation code. Recovery and disruption rates are explicit assumptions, and the model only helps explain the evidence.” |
| Why leave some questions unanswered? | “We only claim what we investigated. An unresolved cause is useful information when the alternative is an unjustified shutdown.” |
| Does a quiet GPU mean it can be removed? | “Not necessarily. We check its memory and workload, then test a smaller allocation before recommending that.” |
| How do you know the dashboard works? | “We checked the official data files, tested the accounting, and launched a fresh copy without an API key.” |

You do not need to invent an answer to a deeper implementation question. Say which part the evidence establishes, which part is an assumption, and refer to the report for the detailed method.
