# Rubric SOP for Subjective Tasks — Six Steps

When the Outcome is a matter of taste (beautiful, usable, polished, well-written) and no unit test can verify it, use this SOP to turn the user's fuzzy taste into a rubric an AI reviewer can execute.

## Why a Rubric Is Needed

AI self-assessment of subjective quality always inflates — no matter how poor the output, it will grade itself "modern" and "premium". The fuzzy concept must be decomposed into explicit dimensions so a reviewer can score against the rubric and force the implementer to keep iterating toward what the user actually wants.

Example: Anthropic decomposed "a beautiful website" into four dimensions — **design quality** (a coherent overall design language), **originality** (deliberate design choices, not default templates), **technical execution** (consistent type hierarchy, spacing, color contrast), and **usability** (users understand the interface and find the primary actions) — and **over-weighted the dimensions the model is usually bad at** (design quality and originality) to correct the model's default tendencies.

## The Six Steps

### 1. Let the AI run a baseline round first
Do not write any criteria yet. Feed 5–10 representative inputs and let the AI run freely. This measures the current baseline capability.

### 2. Personally review every baseline output
Note every point that makes the user frown, **and the concrete reason for the frown**. This produces a landmine list, e.g.:
- The opening has no hook that grabs attention
- The whole piece uses idioms ordinary people never use
- No concrete names or numbers anywhere

### 3. Cluster the frown reasons into dimensions
Group the list into 3–5 dimensions — the skeleton of the rubric. For example, 50 frown reasons might collapse into: loose logic / no human voice / no hook in the opening. Attach a one-line definition to each dimension.

### 4. Turn each dimension into concrete examples
**This is the core of the whole rubric.** Do not write abstract descriptions; write concrete bans the reviewer can catch at a glance:

- ❌ Abstract: "avoid AI flavor", "stay original"
- ✅ Concrete: "Never use an em-dash to join two short clauses for rhythm", "Never use the 'not A, but B' sentence pattern", "Never use Inter, Roboto, Arial, or system fonts", "Never put a gradient overlay on a white card"

Name, one by one, the mistakes the AI keeps making.

### 5. Replace single descriptions with diversified examples
A single example causes overfitting. Anthropic's lesson: the rubric said "museum-grade quality" → every output came out museum-styled. The fix: delete that line and list 11 aesthetic styles (Brutalist, Art Deco, Industrial, Retro Futuristic, …) for the model to choose from by context, ensuring diversity.

### 6. Feed the rubric to the reviewer agent, run, and calibrate by hand
Put the rubric into the goal prompt and instruct the reviewer: "Keep iterating until the rubric above is satisfied. Do not stop."

**Calibration**: Spot-check the first few rounds by hand — compare the reviewer's judgment against what the user sees with their own eyes. A mismatch means the rubric has not yet captured the user's real taste → go back and revise the rubric. After three or four rounds, the definition of "done well" gets teased out line by line.

## Reviewer Setup Notes

- The reviewer must look at **what the user will actually see** (screenshots, the finished artifact), not the code. For web pages, open a browser with Playwright, take screenshots, and score those.
- Iteration is not monotonic — round 10 may beat round 15. As long as the reviewer and implementer keep talking, ambition compounds, and some rounds produce creative leaps a single prompt could never reach.
