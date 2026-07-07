---
name: skill-porting-and-adaptation
description: "Audit, port, and adapt external AI-agent skills into Hermes while preserving dependencies, support files, and platform semantics."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [macos, linux, windows]
metadata:
  hermes:
    tags: [skills, hermes, porting, adaptation, dependency-audit]
    related_skills: [hermes-agent, hermes-plugin-operations]
---

# Skill Porting and Adaptation

Use this when a user asks whether a skill from an external repo can be installed into Hermes, whether it can be installed standalone, or how to adapt skills written for Claude Code, Codex, Gemini, Copilot, OpenCode, Pi, or another harness.

## Core workflow

1. **Inspect the external skill directory, not only `SKILL.md`.**
   - Identify whether the target has only a `SKILL.md` or also `references/`, scripts, templates, prompt files, assets, hooks, or platform plugin metadata.
   - For GitHub repos, clone or fetch the relevant tree and list files under the target skill directory.

2. **Read the target `SKILL.md` and classify references.**
   Look for:
   - Other skill invocations (`/grilling`, `writing-plans`, `domain-modeling`, etc.).
   - Repo-relative file paths (`skills/foo/bar.md`, `scripts/start-server.sh`).
   - Platform-specific tools or fields (`disable-model-invocation`, Claude Code hooks, `AskUserQuestion`, plugin manifests).
   - Terminal states or mandatory handoffs to another skill.

3. **Decide standalone viability.**
   Use this rubric:
   - **Standalone OK:** main `SKILL.md` contains the full workflow and has no hard dependencies, or optional dependencies are clearly marked “if available”.
   - **Standalone but degraded:** core text works, but support files/scripts are missing if installed by raw `SKILL.md` URL.
   - **Not standalone:** the target is a thin wrapper or alias that only invokes another skill; install the core skill too or install only the core skill.
   - **Needs adaptation:** paths, platform tools, or support files assume the original repo layout/harness.

4. **Map external repo layout to Hermes skill layout.**
   Hermes direct URL install generally installs just the `SKILL.md`. If the external skill needs support files, package them under the Hermes skill directory:
   - `references/` for guides, prompt templates, external notes, dependency audit findings.
   - `templates/` for starter files meant to be copied and edited.
   - `scripts/` for executable helper scripts.
   Patch `SKILL.md` to point future agents to those Hermes-local support files.

5. **Respect wrapper/core skill patterns.**
   Many external libraries separate user-invoked wrapper skills from model-invoked reusable skills:
   - Thin wrapper / alias: user-facing entrypoint, often disabled for model invocation.
   - Core reusable skill: actual workflow/discipline other skills compose.
   In Hermes, prefer installing the core reusable skill when the wrapper only exists to preserve slash-command UX. Install both only if the user explicitly wants the original naming or orchestration layer.

6. **Assess redistribution license before publishing adapted skills.**
   When the adapted skill will be committed to a public repo, inspect the upstream repo license (`gh repo view <owner>/<repo> --json licenseInfo` and root `LICENSE` / `NOTICE` files) before pushing. MIT-licensed skill repos may be modified and publicly redistributed, but the copyright and permission notices must be preserved in copies or substantial portions. For public skill collections, add a README attribution section and a `THIRD_PARTY_NOTICES.md` (or equivalent) containing the upstream MIT notices; keep concise source notes in each adapted `SKILL.md`.

7. **Assess overlap with existing Hermes skills.**
   Before creating a new skill, check whether Hermes already has an umbrella skill covering the workflow. If so, prefer patching/adapting the existing skill or adding a support file instead of duplicating a narrow imported skill.

## External skill audit checklist

- [ ] Target repo and path recorded.
- [ ] `SKILL.md` read.
- [ ] Support files under the skill directory listed.
- [ ] Other skill invocations identified.
- [ ] Platform-specific fields/tools identified.
- [ ] Standalone viability classified.
- [ ] Upstream license and any notice requirements checked before public redistribution.
- [ ] Public repo attribution added where needed: README source table plus `THIRD_PARTY_NOTICES.md` or equivalent.
- [ ] Hermes install strategy recommended: raw install, adapted copy, core-only, wrapper+core, or do not install.
- [ ] Any needed path changes listed.

## Common patterns

### Raw `SKILL.md` install is incomplete when support files exist

If an external skill says to read `skills/foo/reference.md` or run `scripts/start-server.sh`, installing only the raw `SKILL.md` into Hermes will leave those references broken. Either make the support feature explicitly optional or package the support files under `references/` / `scripts/` and patch the paths.

### Prefer full repository-path installs for non-default skill roots

When publishing Hermes-adapted skills in a repo that stores them under a non-default root such as `hermes-skills/`, document and test full repository-path installs, for example:

```bash
hermes skills install owner/repo/hermes-skills/superpowers/subagent-driven-development
```

Do not assume `hermes skills tap add owner/repo --path hermes-skills/` is available unless the local CLI help confirms that flag. If tap path selection is not supported in the installed Hermes version, telling users to tap the repo will point Hermes at the default `skills/` root and make the documented short names fail. Prefer the full path form for portable instructions.

### Verify support-file skills after porting

For skills that ship helper scripts or prompt templates, verification should include more than frontmatter checks:

- Validate every `SKILL.md` has `name:` and `description:` frontmatter.
- Confirm every adapted third-party skill directory has its own `NOTICE.md` with the upstream license notice when redistribution is public.
- Run syntax checks for helper scripts (`bash -n`, Python compile, JSON/YAML validation as appropriate).
- Smoke-test deterministic helpers in a temporary fixture repo when practical, e.g. a `task-brief` extractor and `review-package` generator should actually create the expected files.
- Grep for harness-specific leftovers (`superpowers:`, `Claude Code`, `Codex`, `general-purpose subagent`, unsupported slash/plugin commands) and either adapt them to Hermes semantics or explain why they are intentionally retained.

### Thin wrapper skills are not enough by themselves

A skill whose body is essentially “Run `/other-skill`” is not useful alone. Install or port the referenced core skill, or skip the wrapper and use the core skill directly.

### Harness-specific metadata may not mean anything in Hermes

Fields such as `disable-model-invocation: true` can encode useful design intent, but Hermes may not enforce them the same way. Preserve the intent in prose when adapting: e.g. “This is a user-invoked wrapper; do not auto-load it unless explicitly requested.”

## Reference cases

See `references/external-skill-dependency-audit.md` for concrete audit examples including `obra/superpowers` `brainstorming` and `mattpocock/skills` `grill-me` / `grilling`.
