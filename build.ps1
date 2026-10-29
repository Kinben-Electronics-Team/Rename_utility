# Builds dist\RenameUtility.exe in a local virtual environment.
# Usage:  powershell -ExecutionPolicy Bypass -File build.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path .venv)) { python -m venv .venv }
$py = ".venv\Scripts\python.exe"
& $py -m pip install --upgrade pip | Out-Null
& $py -m pip install -r requirements-dev.txt
if ($LASTEXITCODE) { throw "pip install failed" }

& $py -m pytest -q
if ($LASTEXITCODE) { throw "Tests failed; not building." }

& $py -m PyInstaller --noconfirm --clean RenameUtility.spec
if ($LASTEXITCODE) { throw "PyInstaller failed" }

$exe = Get-Item dist\RenameUtility.exe
$hash = (Get-FileHash $exe -Algorithm SHA256).Hash
"{0}  {1}" -f $hash.ToLower(), $exe.Name | Set-Content -Encoding ascii dist\RenameUtility.exe.sha256
Write-Host "Built $($exe.FullName) ($([math]::Round($exe.Length / 1MB, 1)) MB)"
Write-Host "SHA256 $hash"
