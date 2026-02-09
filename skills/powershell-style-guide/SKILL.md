---
name: powershell-style-guide
description: >
  Review and write PowerShell code following community style guide and best practices
  (based on PoshCode/PowerShellPracticeAndStyle). Use when: (1) writing new PowerShell
  scripts, functions, or modules (.ps1, .psm1, .psd1), (2) reviewing PowerShell code
  for style compliance, (3) refactoring PowerShell code, (4) the user asks to "check
  PowerShell style", "review my PowerShell code", "write a PowerShell script/function",
  or any task involving PowerShell scripting where code quality matters.
---

# PowerShell Style Guide

Apply the [PoshCode PowerShell Practice and Style Guide](https://github.com/PoshCode/PowerShellPracticeAndStyle) when writing or reviewing PowerShell code.

## Quick Reference - Essential Rules

### Formatting

- **OTBS braces**: opening `{` on same line, closing `}` on own line
- **4-space indentation** (spaces, not tabs)
- **115 char line limit** - use splatting to break long commands
- **No trailing whitespace**, no semicolons as line terminators
- **Two blank lines** around function/class definitions
- **Single space** around operators and after commas

### Naming

- **PascalCase** everything public: functions, parameters, variables, modules
- **Verb-Noun** for functions (approved verbs from `Get-Verb`)
- **Singular nouns** only
- **Full names** always: `Get-Process -Name Explorer` not `gps Explorer`
- **lowercase** for keywords (`if`, `foreach`) and operators (`-eq`, `-gt`)

### Function Structure

```powershell
function Get-Example {
    <#
        .SYNOPSIS
            Brief description.
        .EXAMPLE
            Get-Example -Name "Test"
            Demonstrates basic usage.
    #>
    [CmdletBinding()]
    [OutputType([string])]
    param(
        # The name to look up
        [Parameter(Mandatory = $true, ValueFromPipelineByPropertyName = $true)]
        [string]$Name
    )
    process {
        # Return objects directly, no 'return' keyword
        "Hello, $Name"
    }
}
```

### Key Patterns

- Always use `[CmdletBinding()]`
- Always add `[OutputType()]`
- Use `SupportsShouldProcess` for state-changing commands
- Use parameter validation attributes (`[ValidateSet()]`, `[ValidateRange()]`, etc.)
- Avoid `return` keyword - output objects directly to pipeline
- Use `process {}` block for pipeline input, not `end {}`
- Strongly type all parameters
- Use `[PSCredential]` for credentials, never plain strings

### Splatting Over Backticks

```powershell
# Correct
$Params = @{
    Path        = $FilePath
    Filter      = "*.log"
    Recurse     = $true
    ErrorAction = "Stop"
}
Get-ChildItem @Params

# Avoid backtick continuation
Get-ChildItem -Path $FilePath `
              -Filter "*.log" `
              -Recurse `
              -ErrorAction Stop
```

### Error Handling

```powershell
try {
    Do-Something -ErrorAction Stop
    Do-More
} catch {
    $err = $_
    Write-Error "Failed: $($err.Exception.Message)"
}
```

### Output Streams

| Command | Purpose |
|---|---|
| Pipeline output | Primary results (objects) |
| `Write-Verbose` | Status/logic details |
| `Write-Debug` | Debugging info for maintainers |
| `Write-Progress` | Real-time progress (ephemeral) |
| `Write-Warning` | Non-terminating warnings |
| `Write-Error` | Non-terminating errors |
| `Write-Host` | ONLY for `Show-`/`Format-` verbs or interactive prompts |

## Review Checklist

When reviewing PowerShell code, check in priority order:

1. **Correctness**: logic bugs, pipeline behavior, error handling
2. **Security**: credential handling (PSCredential), input validation, injection risks
3. **CmdletBinding**: present with OutputType, ShouldProcess where needed
4. **Naming**: Verb-Noun, PascalCase, full names, approved verbs
5. **Formatting**: OTBS braces, 4-space indent, line length, spaces around operators
6. **Documentation**: comment-based help with Synopsis and Example
7. **Parameters**: strongly typed, validation attributes, pipeline support
8. **Output**: no Write-Host misuse, single type per command, raw data from tools

## References

- **Style details** (capitalization, braces, whitespace, naming, comments, function structure): see [references/style-guide.md](references/style-guide.md)
- **Best practices** (tool design, parameters, output, errors, performance, security): see [references/best-practices.md](references/best-practices.md)
