# Week 10 - verdict

**Sunk cost first:** I built the orchestrator, the two specialists and the hand-off accounting this week, and I want that work to have been worth it. It was not, and wanting it to be is exactly the bias that would make me re-run the multi arm until it won one. I am stating the result from the first clean run.

**KILL the policy squad. Keep the single agent.**

1. **Quality: no gain.** On the nine cases with nothing broken both arms score **7/9**. The squad does not answer a single question better than the single agent.
2. **Cost: worse.** On the nine clean cases the squad costs **$0.000644** per question against **$0.000584** - **10% more** for identical quality. (Across all ten it looks like a tie at $0.000596 vs $0.000595, but that average is flattered by E13, where the squad's broken worker made it cheap by failing early. The clean nine are the honest comparison.) The squad sends 22% fewer input tokens thanks to narrower per-worker tool schemas, but emits 63% more output tokens across three components, and output is priced 8x higher.
3. **Latency: worse.** **30 sequential model calls against 20** - 1.5x the round trips, and they cannot be parallelised because the eligibility worker's brief contains the policy worker's output.
4. **Robustness: worse.** Breaking one worker cost the whole case (E13). The manager degraded honestly rather than lying, which is the good outcome of a bad situation, but the single agent has no hand-off to lose.

**When it would be worth it:** if the specialists' jobs were genuinely independent and could run in parallel, or if the toolset grew past what one prompt can route reliably. Neither holds here - 8 of these 10 cases never invoke the second worker at all.

**Caveat:** the 0.8x multiplier is below 1.0 only because of the tool-schema discount on this small set, not because hand-offs are free. On a set where every case used both workers it would exceed 1.0.
