---
name: deep-research
description: Deep multi-step web research using Agent Teams for parallel, coordinated investigation. Use when user needs comprehensive research on a topic ("deep research X", "research X thoroughly", "give me a full analysis of X"), wants a structured research report synthesizing multiple sources, or needs to investigate a topic from multiple angles. Triggers on phrases like "deep research", "thorough research", "comprehensive analysis", "research report", or "/deep-research".
---

# Deep Research (Agent Teams)

Conduct deep, multi-source research using a coordinated Agent Team. Multiple researcher agents work in parallel on different sub-topics, share discoveries via messaging, and the team lead synthesizes findings into a structured report.

## Architecture

```
Team Lead (you)
├── researcher-1  (sub-topic A)
├── researcher-2  (sub-topic B)
├── researcher-3  (sub-topic C)
└── ...up to researcher-6
```

- **Team Lead**: Decomposes topic, creates tasks, spawns researchers, synthesizes final report.
- **Researchers**: `general-purpose` agents with WebSearch/WebFetch. Each owns one sub-topic task. Reports findings back via SendMessage.

## Workflow

### Step 1: Decompose the Research Topic

Break the user's topic into 3-6 independent sub-questions. Select from these angles based on relevance:

| Angle | Example sub-question |
|-------|---------------------|
| Background | What is X? History and origin. |
| Current State | Latest developments, versions, adoption. |
| Comparisons | Alternatives, trade-offs, benchmarks. |
| Best Practices | Recommended approaches, common pitfalls. |
| Ecosystem | Community, tooling, integrations. |
| Future | Roadmap, predictions, emerging trends. |

If the topic is too broad, ask the user to narrow it first.

### Step 2: Create the Research Team

```
TeamCreate:
  team_name: "deep-research-{topic-slug}"
  description: "Deep research on {topic}"
  agent_type: "research-lead"
```

### Step 3: Create Tasks for Each Sub-question

Use TaskCreate for each sub-question:

```
TaskCreate:
  subject: "Research: {sub-question title}"
  description: "{detailed sub-question with scope}"
  activeForm: "Researching {sub-question title}"
```

### Step 4: Spawn Researcher Agents in Parallel

Launch all researchers **in a single message** using the Task tool. Each researcher:

- Has `subagent_type: "general-purpose"`
- Joins the team via `team_name`
- Gets a unique `name` (e.g., `researcher-1`)
- Runs in background via `run_in_background: true`

**Researcher prompt template:**

```
You are a research agent on team "{team-name}". Your name is "{researcher-name}".

## Your Task
Research this question thoroughly: {sub-question}

## Instructions
1. Read the team config at ~/.claude/teams/{team-name}/config.json to discover teammates
2. Claim your task using TaskUpdate (set owner to your name, status to in_progress)
3. Use WebSearch to search at least 3 different queries related to your question
4. Use WebFetch to read the top 2-3 most relevant results
5. Extract key findings with specific facts, numbers, and quotes
6. Note any conflicting information across sources
7. Mark your task as completed using TaskUpdate
8. Send your findings to the team lead using SendMessage

## Output Format
Send findings via SendMessage to the team lead with this structure:

### {Sub-question Title}

**Key Findings:**
- [Finding 1 with specific data]
- [Finding 2 with specific data]
- ...

**Conflicts/Uncertainties:**
- [Any disagreements between sources]

**Sources:**
- [Title](URL) - What this source contributed
```

### Step 5: Monitor and Synthesize

As researchers send back findings via SendMessage:

1. Acknowledge receipt (optional — only if a researcher needs follow-up)
2. After all researchers report back, synthesize into the final report
3. Shut down all researchers via `SendMessage` with `type: "shutdown_request"`

### Step 6: Present the Research Report

Format:

```markdown
# Research Report: [Topic]

## Executive Summary
[2-3 paragraph overview of key findings across all sub-topics]

## Detailed Findings

### [Sub-topic 1]
[Synthesized findings]

### [Sub-topic 2]
[Synthesized findings]

...

## Key Takeaways
- [Most important conclusions]

## Conflicts & Open Questions
- [Areas where sources disagreed or data was insufficient]

## Sources
- [Deduplicated list of all sources with URLs]
```

Offer to dive deeper into any specific sub-topic.

## Guidelines

- **Parallel launch is critical**: Spawn all researchers in a single message.
- **Use background mode**: Set `run_in_background: true` so researchers work concurrently.
- **Source quality**: Prefer official docs, reputable blogs, academic papers, established outlets.
- **Conflict resolution**: Present both perspectives when sources disagree.
- **Recency**: Prioritize recent sources; note publication dates.
- **Language**: Follow CLAUDE.md language rules for the report.
- **Cleanup**: Always shut down teammates when research is complete.
