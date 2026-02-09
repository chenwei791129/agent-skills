# Shell Style Rules — Detailed Reference

Comprehensive rules and examples from the Google Shell Style Guide.

## Table of Contents

- [Comments](#comments)
- [Formatting](#formatting)
- [Quoting](#quoting)
- [Features and Bugs](#features-and-bugs)
- [Naming Conventions](#naming-conventions)
- [Calling Commands](#calling-commands)

---

## Comments

### File Header

Every script must have a top-level comment describing its purpose:

```bash
#!/bin/bash
#
# Perform hot backups of Oracle databases.
```

### Function Comments

All functions in libraries and any non-trivial function require a comment header:

```bash
#######################################
# Clean up files from the backup directory.
# Globals:
#   BACKUP_DIR
#   ORACLE_SID
# Arguments:
#   None
# Outputs:
#   Writes backup status to stdout
# Returns:
#   0 on success, non-zero on error.
#######################################
cleanup() {
  ...
}
```

Required fields vary — include only applicable ones: description, Globals, Arguments, Outputs, Returns.

### Implementation Comments

Comment tricky, non-obvious, interesting, or important code sections. Do not comment obvious code.

### TODO Comments

Use `TODO(username)` format:

```bash
# TODO(mrmonkey): Handle the unlikely edge cases (bug ####)
```

---

## Formatting

### Indentation

- Use 2 spaces for indentation
- Never use tabs (exception: required `<<-` heredoc indentation)
- No trailing whitespace

### Line Length

- Maximum 80 characters per line
- Long strings: use here documents or embedded newlines
- Exception: long URLs or file paths that cannot be split

### Pipelines

```bash
# Short — fits on one line
command1 | command2

# Long — one segment per line, pipe on newline, indented 2 spaces
command1 \
  | command2 \
  | command3 \
  | command4
```

### Loops and Conditionals

`; then` and `; do` go on the same line:

```bash
# if/then/else
if [[ -n "${my_var}" ]]; then
  do_something
elif [[ -d "${my_dir}" ]]; then
  do_other
else
  err "Error"
  exit 1
fi

# for loop
for dir in "${dirs_to_cleanup[@]}"; do
  if [[ -d "${dir}/${ORACLE_SID}" ]]; then
    log_date "Cleaning up old files in ${dir}/${ORACLE_SID}"
    rm "${dir}/${ORACLE_SID}/"*
  fi
done

# while loop
while read -r line; do
  process "${line}"
done < <(generate_lines)
```

### Case Statements

- Indent alternatives by 2 spaces
- One-line alternatives: space after `)` and before `;;`
- Multi-line: pattern, action, and `;;` on separate lines

```bash
case "${expression}" in
  a)
    variable="..."
    some_command "${variable}" "${other_expr}"
    ;;
  absolute)
    actions="relative"
    another_command "${actions}" "${other_expr}"
    ;;
  *)
    err "Unexpected expression '${expression}'"
    ;;
esac
```

Simple one-liners (must fit on one line):

```bash
case "${flag}" in
  verbose) verbose=true ;;
  quiet) verbose=false ;;
  *) err "Unexpected option ${flag}" ;;
esac
```

Avoid `;&` and `;;&` fall-through notations.

### Variable Expansion

- Use `"${var}"` over `"$var"` for multi-character variable names
- Single-char shell specials (`$?`, `$!`, `$#`, `$@`, `$*`, `$-`, `$_`) and single-digit positional params (`$1`–`$9`) don't need braces
- Braces are required for:
  - Positional parameters beyond 9: `"${10}"`
  - String operations: `"${var%.pdf}"`
  - Array elements: `"${array[0]}"`

```bash
# Preferred
echo "Current: ${current_version}, Next: ${next_version}"

# Acceptable for simple cases, but be consistent
echo "HOME is $HOME"
```

---

## Quoting

### Always Quote

- Strings with variables or command substitutions
- Strings with spaces or shell metacharacters
- Integer-valued variables (quote them as strings too)

```bash
# Correct
flag="$(some_command and target)"
echo "${flag}"

# Correct
readonly USE_INTEGER='true'

# Correct
echo 'Hello stranger, and well met.'
```

### Never Quote

- Integer literals for `(( ))`: `if (( my_var > 3 )); then`
- Inside `[[ ]]` for the variable being tested (right side may still need quotes for pattern vs string)
- Parameters that must allow word splitting (rare — document why)

### Arrays for Safe Lists

```bash
# Correct — each element preserved
declare -a flags=(--hierarchical --resolve)
flags+=(--resolve)
some_command "${flags[@]}" "$@"

# Wrong — word splitting issues
flags='--hierarchical --resolve'
some_command ${flags}
```

---

## Features and Bugs

### ShellCheck

Always run [ShellCheck](https://www.shellcheck.net/) on scripts to catch common bugs and warnings.

### Command Substitution

```bash
# Correct
var="$(command)"

# Wrong — hard to nest
var=`command`
```

### Test Constructs

```bash
# Correct — no pathname expansion or word splitting issues
if [[ "${my_var}" == "val" ]]; then
  do_something
fi

# Correct — explicit length tests
if [[ -z "${my_var}" ]]; then   # zero length
if [[ -n "${my_var}" ]]; then   # non-zero length

# Wrong — filler characters
if [[ "x${my_var}" == "xval" ]]; then
```

### Wildcard Expansion

```bash
# Correct — safe for filenames starting with -
rm ./*

# Dangerous — -f could be interpreted as a flag
rm *
```

### Eval

Never use `eval`. It munges input and can execute unexpected code:

```bash
# Wrong
eval "echo ${variable}"

# Correct alternatives: use arrays, printf, or parameter expansion
```

### Arrays

Use bash arrays for lists of elements:

```bash
# Correct
declare -a my_list=('item1' 'item2' 'item3')
for item in "${my_list[@]}"; do
  process "${item}"
done

# Wrong — word splitting, glob expansion issues
my_list='item1 item2 item3'
```

### Pipes to While

```bash
# Correct — process substitution preserves variable scope
last_line='NULL'
while read -r line; do
  last_line="${line}"
done < <(your_command)
echo "Last line: ${last_line}"

# Correct — readarray/mapfile
readarray -t lines < <(your_command)
for line in "${lines[@]}"; do
  process "${line}"
done

# Wrong — while runs in subshell, variables lost
last_line='NULL'
your_command | while read -r line; do
  last_line="${line}"  # lost after loop
done
echo "Last line: ${last_line}"  # prints NULL
```

### Arithmetic

```bash
# Correct
(( i = 10 * j + 400 ))
result=$(( i * 2 ))

# Wrong
i=$(expr 10 \* "$j" + 400)
let "i = 10 * j + 400"
i=$[ 10 * j + 400 ]
```

**Caution with `set -e`**: Avoid `(( ))` as a standalone statement when the expression may evaluate to zero — it returns exit code 1, causing the script to exit under `set -e`:

```bash
(( count = 0 ))  # exits under set -e because result is 0!
count=$(( 0 ))   # safe alternative
```

### Aliases

Never use aliases in scripts. Use functions instead:

```bash
# Wrong
alias ll='ls -la'

# Correct
ll() {
  ls -la "$@"
}
```

---

## Naming Conventions

### Functions

```bash
# Single-word package
my_func() { ... }

# Multi-level package
mypackage::my_func() { ... }

# Braces on same line, parentheses required
# function keyword optional but be consistent within a file
```

### Variables and Constants

```bash
# Regular variables — lowercase
local my_var="value"
my_var="value"

# Loop variables — descriptive
for zone in "${zones[@]}"; do
  something_with "${zone}"
done

# Constants — uppercase, declared early
# Prefer readonly/export over declare equivalents for clarity
readonly PATH_TO_FILES='/some/path'
readonly MAPPING_KEY1="value1"

# When associative arrays are needed, declare -rA is acceptable
declare -rA MAPPING=(
  [key1]="value1"
  [key2]="value2"
)

# Export only when needed
export ORACLE_SID='PROD'
```

### Local Variables

Always use `local` for function-specific variables:

```bash
my_func() {
  local name="$1"

  # Separate declaration from command substitution
  local my_var
  my_var="$(my_func2)" || return

  # This masks the return code of my_func2
  # local my_var="$(my_func2)"  # WRONG
}
```

---

## Calling Commands

### Return Values

```bash
# Check return values explicitly
if ! mv "${file_list[@]}" "${dest_dir}/"; then
  err "Unable to move files"
  exit 1
fi

# Or use ||
mv "${file_list[@]}" "${dest_dir}/" || { err "Move failed"; exit 1; }

# For pipelines — PIPESTATUS resets after any command
tar -cf - ./* | gzip > out.tar.gz
declare -a pipe_status=("${PIPESTATUS[@]}")
if (( pipe_status[0] != 0 )); then
  err "tar failed with status ${pipe_status[0]}"
fi
```

### Builtins vs External Commands

Prefer builtins and parameter expansion:

```bash
# String manipulation — use parameter expansion
dirname="${path%/*}"
basename="${path##*/}"
extension="${filename##*.}"
no_extension="${filename%.*}"

# Arithmetic — use (( ))
(( count++ ))
total=$(( price * quantity ))

# Regex — use [[ =~ ]]
if [[ "${input}" =~ ^[0-9]+$ ]]; then
  echo "Numeric"
fi

# Avoid external commands for simple operations
# sed, awk, expr, basename, dirname — use builtins when possible
```
