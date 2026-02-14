param(
    [Parameter(Mandatory = $true)]
    [string]$Message
)

$ErrorActionPreference = "Stop"

function Run-Git {
    param(
        [Parameter(Mandatory = $true, ValueFromRemainingArguments = $true)]
        [string[]]$GitArgs
    )

    & git @GitArgs
    if ($LASTEXITCODE -ne 0) {
        throw "git $($GitArgs -join ' ') failed."
    }
}

Write-Host "==> Branch:"
Run-Git branch --show-current

Write-Host "==> Status:"
git status --short

Write-Host "==> Adding files..."
Run-Git add .

# Safety check: refuse if .venv got staged somehow
$staged = git diff --cached --name-only
if ($staged -match '(^|/)\.venv(/|$)') {
    throw "Refusing to commit: .venv is staged. Fix .gitignore / unstage .venv first."
}

if ([string]::IsNullOrWhiteSpace(($staged | Out-String))) {
    Write-Host "No staged changes. Nothing to commit."
    exit 0
}

Write-Host "==> Committing..."
Run-Git commit -m $Message

Write-Host "==> Pushing..."
Run-Git push

Write-Host "✅ Done."