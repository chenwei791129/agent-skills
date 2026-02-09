# PowerShell Best Practices Reference

Based on [PoshCode/PowerShellPracticeAndStyle](https://github.com/PoshCode/PowerShellPracticeAndStyle).

## Table of Contents

- [Tool vs Controller Design](#tool-vs-controller-design)
- [Reusability](#reusability)
- [Parameter Blocks](#parameter-blocks)
- [Output and Formatting](#output-and-formatting)
- [Error Handling](#error-handling)
- [Performance](#performance)
- [Security](#security)
- [.NET Interop](#net-interop)
- [Versioning](#versioning)

---

## Tool vs Controller Design

- **Tools** (functions/modules): reusable, accept input via parameters, output raw data to pipeline
- **Controllers** (automation scripts): orchestrate tools, may format output for specific audiences

Tools should output raw data (e.g., bytes not GB). Controllers may reformat for readability.

## Reusability

- Modularize working code into functions stored in script modules
- Use standard `Verb-Noun` naming with approved verbs (`Get-Verb`)
- Follow PowerShell standard parameter naming (e.g., `$ComputerName` not `$Param_Computer`)
- Prefer native PowerShell commands over reinventing existing functionality
- Wrap non-PowerShell tools in advanced functions/cmdlets
- Document reasons for using non-PowerShell approaches

## Parameter Blocks

### CmdletBinding

Always use `[CmdletBinding()]`. Benefits:
- Enables `-Verbose`, `-Debug`, `-ErrorAction`, and other common parameters
- Supports `-?` for help
- Prevents accidental execution when user just wants help

### ShouldProcess

Add `SupportsShouldProcess` for state-changing commands:

```powershell
[CmdletBinding(SupportsShouldProcess, ConfirmImpact = "Medium")]
param([switch]$Force)

process {
    if ($PSCmdlet.ShouldProcess($target, "action description")) {
        # perform the action
    }
}
```

### Strong Typing

- Always type parameters explicitly
- Avoid `[string]` or `[object]` on pipeline or parameter-set-differentiating params
- Use `[PSCredential]` for credentials (with `[Credential()]` attribute on older PS versions)
- Switch parameters: no default values, design so setting them enables less common behavior

### Pipeline Support

- Use `ValueFromPipelineByPropertyName` generously
- Add `[Alias()]` to match common property names
- Pipeline values only available in `process {}` block

### Help Requirements

- Always include `.SYNOPSIS` and/or `.DESCRIPTION`
- Always provide at least one `.EXAMPLE` (code first, then explanation)
- Document every parameter (inline comment above parameter preferred)

## Output and Formatting

- Do NOT use `Write-Host` for script output (only for `Show-`/`Format-` verbs or interactive prompts)
- Use `Write-Progress` for progress (ephemeral, real-time)
- Use `Write-Verbose` for status/logic details (useful but not necessary)
- Use `Write-Debug` for debugging/maintenance info
- Use `.format.ps1xml` for custom object formatting, not `Format-*` cmdlets inside functions
- Output one type of object per command; use `[OutputType()]` attribute
- Exception: internal functions may return multiple types for efficiency

## Error Handling

1. Use `-ErrorAction Stop` on cmdlets to generate trappable exceptions
2. Set `$ErrorActionPreference = 'Stop'` before non-cmdlet calls, reset to `'Continue'` after
3. Put entire transactions in `try` block instead of using flags
4. Avoid `$?` - it doesn't reliably indicate errors
5. Avoid testing null variables as error conditions when possible
6. Copy `$_` or `$Error[0]` to your own variable immediately in `catch` blocks

```powershell
# Correct pattern
try {
    Do-Something -ErrorAction Stop
    Do-This
    Set-That
} catch {
    $errorRecord = $_
    Handle-Error -ErrorRecord $errorRecord
}
```

## Performance

- **Measure** before optimizing: use `Measure-Command` or Profiler module
- **Trade-off**: readability vs performance - favor readability for small data sets
- General speed hierarchy: Language features > .NET methods > Script > Pipeline cmdlets
- `foreach` statement is faster than `ForEach-Object` cmdlet
- For large files, use `StreamReader` instead of `Get-Content` (or wrap in cmdlets)
- Pipeline streaming avoids memory issues for large data sets

## Security

### Credentials

- Always use `[PSCredential]` - never plain string passwords
- Accept credentials as parameters, never call `Get-Credential` inside functions
- Decrypt credentials at the point of use, not into variables

```powershell
param(
    [System.Management.Automation.PSCredential]
    [System.Management.Automation.Credential()]
    $Credential
)

# Decrypt at point of use
$Insecure.SetPassword($Credential.GetNetworkCredential().Password)
```

### Secure Strings

- Use `SecureString` for sensitive non-credential strings
- Save credentials with `Export-CliXml` (DPAPI protected, user+machine bound)
- Convert with `ConvertFrom-SecureString`/`ConvertTo-SecureString` for disk storage

## .NET Interop

- Prefer native PowerShell when possible
- When using .NET: document the reason in comments
- Wrap .NET calls in advanced functions for reusability

## Versioning

- Write for the lowest PowerShell version possible for compatibility
- Use `#Requires -Version X.X` at script top
- Set `PowerShellVersion` in module manifests (`.psd1`)
- Don't sacrifice functionality/performance just for older version compatibility
