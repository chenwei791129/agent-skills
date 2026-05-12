# Project Instructions

## Skills Maintenance

After adding, removing, or renaming a skill in `skills/`, update the **Available Skills** table in `README.md` to keep it in sync.

## Skill Frontmatter

When writing `description:` in a `SKILL.md` frontmatter:
- Wrap in single quotes if the value contains `: ` (colon + space) or `"..."` double quotes, otherwise strict YAML parsers (e.g. `gh skill publish`) will fail.
- Verify with `gh skill publish --dry-run` before committing.
