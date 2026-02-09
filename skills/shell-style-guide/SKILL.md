---
name: shell-style-guide
description: "Review shell/bash code for adherence to Google Shell Style Guide. Use when the user requests a code review of shell scripts (.sh, .bash), writing new shell scripts, fixing shell script issues, or checking shell code against style guidelines. Trigger phrases include: review this shell script, check shell style, write a bash script, review my shell code, or any task involving shell/bash scripting where code quality and consistency matter."
---

# Shell Style Guide

Review and write shell scripts following the [Google Shell Style Guide](https://google.github.io/styleguide/shellguide.html).

## When Writing Shell Scripts

### Use Bash Only

- Use `#!/bin/bash` with minimal flags
- Set shell options via `set` rather than shebang flags (e.g., `set -o errexit`, `set -o nounset`)
- Caution: `(( ))` evaluating to zero returns non-zero, which causes exit under `set -e`
- If a script exceeds ~100 lines or has complex control flow, recommend rewriting in Python or Go

### File Conventions

- Executables: no extension (strongly preferred) or `.sh`
- Libraries (sourced only): `.sh` extension, not executable
- SUID/SGID: forbidden — use `sudo` instead

### Error Output

Direct all error messages to STDERR:

```bash
err() {
  echo "[$(date +'%Y-%m-%dT%H:%M:%S%z')]: $*" >&2
}
```

## Review Checklist

When reviewing shell code, check these categories in order:

1. **Critical bugs** — unquoted variables, missing error handling, unsafe `eval`
2. **Formatting** — 2-space indent, 80-char line limit, pipeline style
3. **Naming** — lowercase_with_underscores for functions/variables, UPPER_CASE for constants
4. **Best practices** — `[[ ]]` over `[ ]`, `$(cmd)` over backticks, arrays over space-delimited strings
5. **Structure** — `main` function pattern, functions grouped at top, comments on non-obvious logic

For detailed rules and examples in each category, see [references/style-rules.md](references/style-rules.md).

## Key Rules Summary

### Formatting

- **Indent**: 2 spaces, no tabs
- **Line length**: max 80 characters
- **Pipelines**: one-liners stay on one line; multi-segment pipelines split with `|` on newline
- **Loops/conditionals**: `; then` / `; do` on same line as `if` / `for` / `while`

### Quoting & Variables

- Always quote strings with variables, command substitutions, spaces, or metacharacters
- Prefer `"${var}"` over `"$var"` (exception: single-char specials like `$?`, `$!`, `$@` don't need braces)
- Use `"$@"` over `$*`

### Features

- `[[ ... ]]` over `[ ... ]` — avoids pathname expansion and word splitting
- `$(command)` over backticks — cleaner nesting
- `(( ... ))` for arithmetic — never `let`, `$[ ]`, or `expr`
- Use arrays for lists — avoid space-delimited strings
- Avoid `eval` — use safer alternatives
- Use process substitution `< <(cmd)` or `readarray` instead of piping to `while`
- Use ShellCheck to catch common bugs

### Naming

| Element | Convention | Example |
|---------|-----------|---------|
| Functions | `lower_snake_case` | `get_user_name()` |
| Variables | `lower_snake_case` | `local user_name` |
| Constants | `UPPER_SNAKE_CASE` | `readonly MAX_RETRIES=3` |
| Package separator | `::` | `mypackage::my_func()` |

### Structure

```bash
#!/bin/bash
# File header comment describing the script's purpose.

# Set shell options instead of using shebang flags.
# Note: set -e causes (( )) returning 0 to exit. Use with caution.

# Constants
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Functions (grouped together, before main)
parse_args() { ... }
validate_input() { ... }

main() {
  parse_args "$@"
  validate_input
  # ...
}

main "$@"
```

### Local Variables

- Declare with `local` in functions
- Separate declaration from assignment when capturing command output:

```bash
# Correct — exit code is checkable
local my_var
my_var="$(my_func)"

# Wrong — local always returns 0, masking errors
local my_var="$(my_func)"
```

### Return Values & Pipelines

- Always check return values
- For pipelines, check `PIPESTATUS` immediately (it resets on next command):

```bash
tar -cf - ./* | gzip > archive.tar.gz
if (( PIPESTATUS[0] != 0 || PIPESTATUS[1] != 0 )); then
  err "Pipeline failed"
fi
```

### Builtins Over External Commands

Prefer shell builtins for efficiency:

```bash
# Prefer
addition=$(( x + y ))
[[ "${input}" =~ ^[0-9]+$ ]]
"${str##*/}"   # basename

# Avoid
addition=$(expr "${x}" + "${y}")
echo "${input}" | grep -q '^[0-9]+$'
"$(basename "${str}")"
```
