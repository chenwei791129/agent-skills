---
name: pre-goal
description: 'Use when the user is about to launch /goal (or any long-running autonomous agent task) and the task is still vaguely defined, mentions "pre-goal" / "define the goal" / "write a goal prompt", or complains that a previous /goal run drifted off course, wrapped up too early, or produced unsatisfying results. Guides the user to pin down the definition of done before launching.'
---

# Pre-Goal: Turn a Vague Task into a Long-Running Goal Prompt

## Overview

A goal run succeeds or fails on how precisely "done" (the Definition of Done) is defined. A vague definition forces the AI to guess what "good" means → it wraps up in three minutes with output the user never wanted. This skill guides the user to nail down five elements before launching `/goal`.

## The Iron Law

**Never skip the interview and generate the goal prompt for the user.**

The task the user brings is necessarily vague ("make it better", "make it prettier") — that is exactly why they came to you. Filling in the details yourself = you defining their Definition of Done = output they will not be satisfied with.

**No exceptions:**
- Do not skip because "the task looks simple"
- Do not skip because "there is enough information in context"
- Do not write a full prompt first and then ask "want any changes?" — the order is confirm first, assemble second

## Process

1. **Gather clues**: Read the user's task description. Mine the codebase and conversation history for usable facts (existing test commands, performance tools, directory layout) to use as proposal material.
2. **Propose + confirm, element by element**: For each of the five elements below, draft 1–3 **concrete proposals** based on the clues, then use AskUserQuestion to let the user pick or revise. Never throw open-ended questions at a blank page — you propose, the user corrects.
3. **Branch for subjective tasks**: If the Outcome is a matter of taste (beautiful, usable, polished, engaging), plain-text criteria cannot be verified. The Verification element must produce a rubric → follow the six-step SOP in [references/rubric-sop.md](references/rubric-sop.md).
4. **Assemble**: Once all five elements are confirmed, compose the goal prompt using the template below and show it to the user.
5. **Deliver**: After the user approves, output the final prompt and remind them to paste it into `/goal`. **Do not launch /goal yourself.**

## The Five Elements — Quality Bar

| Element | Question it answers | Quality bar | Bad → Good |
|---|---|---|---|
| **Outcome** | What state counts as done? | Observable, with numbers or a decidable boundary | "Make search better" → "Search first-paint response p95 ≤ 300ms; queries with up to 2 typos still match" |
| **Verification** | How is completion proven? | A command/tool/rubric the agent can run by itself | "Tests pass" → "`npm run test:search` all green, and the k6 script measures p95 ≤ 300ms" |
| **Constraints** | What must NOT be done? | Named no-go zones: file scope, forbidden actions | "Don't break things" → "Only touch `src/search/**` and its tests; no new dependencies; no API schema changes" |
| **Iteration Policy** | What must each round leave behind? | Per round: what changed, verification result (data), next most promising direction | None → "Append to `NOTES.md` at the end of every round" |
| **Error Handling** | When should it stop and report instead of looping? | Explicit stop conditions + report format (what was tried / where it is stuck / what is needed) | "Deal with problems as they come" → "Verification tool won't run, or same error for 3 consecutive rounds → stop and report" |

## Fast Path (when the user is in a hurry)

When the user does not want to answer item by item, **you may compress the questions, but you may not guess on the user's behalf**. Rules:

- **Outcome, Verification, and Constraints must come from the user** — these three carry the user's taste and intent; guessing them is always wrong. Compress them into a single AskUserQuestion (multiple questions) asked all at once.
- **Iteration Policy and Error Handling may fall back to standard defaults**, but mark them in the final prompt so the user can confirm at a glance:
  - Iteration Policy default: append to `NOTES.md` each round: what changed / verification result / next direction
  - Error Handling default: verification tool won't run, same problem for 3 consecutive rounds with no progress, or all known approaches exhausted without reaching the target → stop and report what was tried / where it is stuck / what is needed

## Goal Prompt Template

```markdown
# Goal
<one-sentence done state (Outcome)>

## Definition of Done
- <verifiable condition 1>
- <verifiable condition 2>

## Verification
<command/tool to verify each round; for subjective tasks, attach the rubric and scoring method>

## Constraints
- May touch: <scope>
- Must not touch: <no-go zones>
- <other forbidden actions>

## Iteration Policy
Keep iterating until the Definition of Done is met. At the end of every round, append to <NOTES.md>:
1. What this round changed
2. Verification result (concrete data / score)
3. The next most promising direction to try

## Stop Conditions
On any of the following, stop and report "what was tried, where it is stuck, what information is needed to continue":
- <verification tool won't run>
- <same problem for N consecutive rounds with no progress>
- <all known approaches exhausted without reaching the target>
```

## Common Mistakes

| Mistake | Consequence | Fix |
|---|---|---|
| Generating the prompt without interviewing | AI defines the DoD itself; output misses expectations | Propose, then confirm each of the five elements |
| Verification written as "ensure quality" | The reviewer has nothing to score against; self-grades always pass | Objective tasks get runnable commands; subjective tasks get a rubric |
| A linear phase plan instead of an iteration loop | One pass and done; never iterates to the target | Frame as a loop: "keep going until the Outcome is met" |
| No stop conditions | Infinite loop burning tokens, or stuck and guessing blindly | At least one "stop after N rounds without progress" |
| Rubric written as abstract adjectives ("stay original") | The reviewer cannot detect violations | Name concrete banned examples, and diversify them to avoid overfitting |

## Red Flags — Stop When You Catch Yourself Thinking

- "This task is clear enough, no need to ask" → Clear to you is not clear, period. Propose and let the user confirm.
- "I'll draft a full version first, it's faster for them to edit" → Dump a whole prompt at once and the user will just say "fine". Confirm element by element.
- "Verification can be figured out during the run" → A goal without verification criteria always wraps up early.
