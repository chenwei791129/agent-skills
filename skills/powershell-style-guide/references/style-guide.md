# PowerShell Style Guide Reference

Based on [PoshCode/PowerShellPracticeAndStyle](https://github.com/PoshCode/PowerShellPracticeAndStyle).

## Table of Contents

- [Capitalization Conventions](#capitalization-conventions)
- [Brace Style (OTBS)](#brace-style-otbs)
- [CmdletBinding](#cmdletbinding)
- [Block Ordering](#block-ordering)
- [Indentation](#indentation)
- [Line Length](#line-length)
- [Blank Lines and Whitespace](#blank-lines-and-whitespace)
- [Spaces](#spaces)
- [Semicolons](#semicolons)
- [Naming Conventions](#naming-conventions)
- [Documentation and Comments](#documentation-and-comments)
- [Function Structure](#function-structure)
- [Readability](#readability)

---

## Capitalization Conventions

- **PascalCase** for all public identifiers: module names, function/cmdlet names, class/enum/attribute names, public fields/properties, global variables, constants, parameters
- **lowercase** for language keywords (`foreach`, `dynamicparam`, `if`, `else`, `try`, `catch`)
- **lowercase** for operators (`-eq`, `-match`, `-gt`)
- **UPPERCASE** for comment-based help keywords (`.SYNOPSIS`, `.DESCRIPTION`, `.PARAMETER`)
- Two-letter acronyms: both capitalized (`$PSBoundParameters`, `Get-PSDrive`)
- Optional: **camelCase** for private/local variables within functions to distinguish from parameters

```powershell
# Correct
function Get-UserProfile {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$UserName
    )
    # local variable in camelCase (optional convention)
    $userProfile = Get-Item -Path "\\server\profiles\$UserName"
    $userProfile
}
```

## Brace Style (OTBS)

Use One True Brace Style: opening brace on end of line, closing brace at beginning of line.

```powershell
# Correct - OTBS
function Test-Code {
    [CmdletBinding()]
    param(
        [int]$Value
    )
    end {
        if ($Value -gt 10) {
            "Greater"
        } else {
            "Lesser"
        }
    }
}

# Exception: small scriptblocks on one line
Get-ChildItem | Where-Object { $_.Length -gt 10mb }
```

## CmdletBinding

Always start scripts and functions with `[CmdletBinding()]`:

```powershell
[CmdletBinding()]
param()
process {
}
end {
}
```

## Block Ordering

Prefer: `param()`, `begin`, `process`, `end` - in execution order for clarity.

Do not use anonymous end blocks or the `filter` keyword - be explicit.

## Indentation

Use 4 spaces per indent level. Configure editor to insert spaces, not tabs.

Continuation lines may indent more than one level or align with the previous line:

```powershell
function Test-Code {
    foreach ($base in 1,2,4,8,16) {
        [System.Math]::Pow($base,
                           $exponent)
    }
}
```

## Line Length

Limit to 115 characters. Use splatting or implied line continuation inside parentheses/brackets/braces instead of backticks:

```powershell
# Preferred - splatting
$Params = @{
    Class        = "Win32_LogicalDisk"
    Filter       = "DriveType=3"
    ComputerName = "SERVER2"
}
Get-WmiObject @Params

# Acceptable - parenthetical continuation
Write-Host -Object ("This is a long message. " +
                     "Split across lines.")
```

## Blank Lines and Whitespace

- **Two** blank lines before/after function and class definitions
- **One** blank line between method definitions within a class
- End each file with a single blank line
- No trailing whitespace on lines

## Spaces

- Single space around parameter names and operators (including `-eq`, `-gt`, `=`, `+`)
- Single space after commas and semicolons
- Single space inside `$( ... )` and `{ ... }` (scriptblocks), but NOT inside `${...}` (variable delimiters)
- No unnecessary spaces inside `()` or `[]`
- Exception: no space for colon syntax on switch params: `-Wait:($ReadCount -gt 0)`
- Exception: no space for unary operators: `$i++`, `AddDays(-1)`

```powershell
# Correct
$variable = Get-Content -Path $FilePath -Wait:($ReadCount -gt 0) -TotalCount ($ReadCount * 5)
$yesterdaysDate = (Get-Date).AddDays(-1)

# Subexpressions with inner spaces
"There are $( (Get-ChildItem).Count ) files."
```

## Semicolons

Do not use semicolons as line terminators. They are unnecessary in PowerShell.

```powershell
# Correct
$Options = @{
    Margin   = 2
    Padding  = 2
    FontSize = 24
}
```

## Naming Conventions

- Use full command names, never aliases (`Get-Process` not `gps`)
- Use full parameter names (`-Name` not positional)
- Use `Verb-Noun` format with PascalCase (use `Get-Verb` for approved verbs)
- Use singular nouns
- Use `$PSScriptRoot` based paths, avoid relative paths and `~`
- Use `Join-Path` or string interpolation for path construction

```powershell
# Correct
Get-Process -Name Explorer
Get-Content -Path (Join-Path -Path $PSScriptRoot -ChildPath "README.md")

# Wrong
gps Explorer
Get-Content .\README.md
```

## Documentation and Comments

### Comment-Based Help

Place inside the function, above `param`:

```powershell
function Get-Example {
    <#
        .SYNOPSIS
            Brief description of the function.

        .DESCRIPTION
            Longer description.

        .EXAMPLE
            Get-Example -Name "Test"

            Shows how to use the function.

        .NOTES
            Detailed implementation notes.
    #>
    [CmdletBinding()]
    param(
        # Description of the Name parameter
        [Parameter(Mandatory = $true)]
        [string]$Name
    )
    # ...
}
```

### Rules

- Comments in English, complete sentences
- Explain the **why**, not the **what**
- Block comments for groups of code, not per-line comments
- Inline comments separated by at least 2 spaces, aligned when possible
- Use `<# ... #>` for long block comments, with delimiters on own lines
- Document every parameter (preferably inline above the parameter in the param block)
- Always provide at least one `.EXAMPLE`

## Function Structure

### Simple Functions

```powershell
function MyFunction ($param1, $param2) {
    # ...
}
```

### Advanced Functions

- Use `Verb-Noun` naming with `Get-Verb` approved verbs
- Always use `[CmdletBinding()]`
- Always specify `[OutputType()]`
- Do NOT use `return` keyword - place objects directly in pipeline
- Return objects in `process {}`, not `begin {}` or `end {}`
- Use parameter validation attributes instead of body validation
- When using `ParameterSetName`, set `DefaultParameterSetName` in `CmdletBinding`

```powershell
function Get-User {
    [CmdletBinding(DefaultParameterSetName = "ID")]
    [OutputType("System.Int32", ParameterSetName = "ID")]
    [OutputType([String], ParameterSetName = "Name")]
    param(
        [Parameter(Mandatory = $true, ParameterSetName = "ID")]
        [int[]]$UserID,

        [Parameter(Mandatory = $true, ParameterSetName = "Name")]
        [string[]]$UserName
    )
    process {
        # Return objects here, not in end {}
    }
}
```

### Parameter Validation Attributes

Use these instead of manual validation in the function body:

| Attribute | Purpose |
|---|---|
| `[AllowNull()]` | Allow null for mandatory params |
| `[AllowEmptyString()]` | Allow empty string for mandatory params |
| `[AllowEmptyCollection()]` | Allow empty collection for mandatory params |
| `[ValidateCount(min, max)]` | Validate array element count |
| `[ValidateLength(min, max)]` | Validate string length |
| `[ValidatePattern("regex")]` | Validate against regex |
| `[ValidateRange(min, max)]` | Validate numeric range |
| `[ValidateScript({...})]` | Validate with custom script |
| `[ValidateSet("A", "B")]` | Validate against allowed values |
| `[ValidateNotNull()]` | Reject null |
| `[ValidateNotNullOrEmpty()]` | Reject null or empty |

## Readability

### Avoid Backticks

Use splatting instead of backtick line continuation:

```powershell
# Avoid
Get-WmiObject -Class Win32_LogicalDisk `
              -Filter "DriveType=3" `
              -ComputerName SERVER2

# Prefer
$Params = @{
    Class        = "Win32_LogicalDisk"
    Filter       = "DriveType=3"
    ComputerName = "SERVER2"
}
Get-WmiObject @Params
```
