# Project Instructions

## Skills Maintenance

After adding, removing, or renaming a skill in `skills/`, update the **Available Skills** table in `README.md` to keep it in sync.

## Hermes Skills

Skills under `hermes-skills/` target the Hermes Agent, not `gh skill`:
- Organize them by category: `hermes-skills/<category>/<skill-name>/SKILL.md` (e.g. `superpowers/`, `platform/`).
- After adding, removing, or renaming one, update the **Available Hermes Skills** table in `README.md`, using the `<category>/<skill-name>` path as the skill name.
- They are installed with `hermes skills install chenwei791129/agent-skills/hermes-skills/<category>/<skill-name>`; do not add them to the `gh skill` sections of `README.md`.

## Skill Frontmatter

When writing `description:` in a `SKILL.md` frontmatter:
- Wrap in single quotes if the value contains `: ` (colon + space) or `"..."` double quotes, otherwise strict YAML parsers (e.g. `gh skill publish`) will fail.
- Verify with `gh skill publish --dry-run` before committing.
