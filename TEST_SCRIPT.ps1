# NovaXinWei Test Script
# Run: powershell -ExecutionPolicy Bypass -File TEST_SCRIPT.ps1

$ErrorActionPreference = "Continue"
$pass = 0
$fail = 0

function Test-Step {
    param([string]$name, [scriptblock]$test)
    $result = & $test
    if ($result) {
        Write-Host "PASS: $name" -ForegroundColor Green
        $script:pass++
    } else {
        Write-Host "FAIL: $name" -ForegroundColor Red
        $script:fail++
    }
}

Write-Host "=== NovaXinWei Test Suite ===" -ForegroundColor Cyan
Write-Host ""

# 1. Import test
Test-Step "Engine import" { python -c "from novaxinwei.engine import fetch; print('ok')" 2>$null }
Test-Step "Channels import" { python -c "from novaxinwei.channels import ALL_CHANNELS; print(len(ALL_CHANNELS))" 2>$null }
Test-Step "CLI import" { python -c "from novaxinwei.cli import main; print('ok')" 2>$null }

# 2. Channel count
$chCount = python -c "from novaxinwei.channels import ALL_CHANNELS; print(len(ALL_CHANNELS))"
Test-Step "11 channels registered" { $chCount -eq "11" }

# 3. CLI commands
Test-Step "CLI --help" { python -m novaxinwei --help 2>$null | Out-Null; $LASTEXITCODE -eq 0 }
Test-Step "CLI check" { python -m novaxinwei check 2>$null | Out-Null; $LASTEXITCODE -eq 0 }
Test-Step "CLI dorks shodan" { python -m novaxinwei dorks shodan camera 2>$null | Out-Null; $LASTEXITCODE -eq 0 }
Test-Step "CLI dorks github" { python -m novaxinwei dorks github password 2>$null | Out-Null; $LASTEXITCODE -eq 0 }

# 4. No source name references
$refs = grep -r "insane_search\|agent_reach\|Agent-Reach" --include="*.py" . 2>$null | grep -v "references/" | grep -v "utils.py.*#"
Test-Step "No source name references" { $refs -eq "" }

# 5. Compile all
$compileOk = python -c "
import py_compile, os, sys
errors = []
for root, dirs, files in os.walk('.'):
    if '__pycache__' in root or 'references' in root:
        continue
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            try:
                py_compile.compile(path, doraise=True)
            except py_compile.PyCompileError as e:
                errors.append(str(e))
print(len(errors))
" 2>$null
Test-Step "All .py compile" { $compileOk -eq "0" }

# 6. File counts
$pyCount = python -c "import os; print(sum(1 for r,d,fs in os.walk('.') if '__pycache__' not in r for f in fs if f.endswith('.py')))" 2>$null
Test-Step "40 .py files" { $pyCount -eq "40" }

# Summary
Write-Host ""
Write-Host "=== Results: $pass PASS, $fail FAIL ===" -ForegroundColor $(if ($fail -eq 0) { "Green" } else { "Red" })
exit $fail
