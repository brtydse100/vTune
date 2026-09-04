param([string]$Python = "py -3.12")

$ErrorActionPreference = "Stop"
$repository = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$validation = Join-Path $repository ".validation-venv"
$wheelValidation = Join-Path $repository ".wheel-validation-venv"

function Invoke-Python([string]$Executable, [string[]]$Arguments) {
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Python command failed with exit code $LASTEXITCODE" }
}

Push-Location $repository
try {
    if (Test-Path -LiteralPath $validation) { Remove-Item -LiteralPath $validation -Recurse -Force }
    if (Test-Path -LiteralPath $wheelValidation) { Remove-Item -LiteralPath $wheelValidation -Recurse -Force }
    $distribution = Join-Path $repository "dist"
    if (Test-Path -LiteralPath $distribution) { Remove-Item -LiteralPath $distribution -Recurse -Force }

    $launcher = $Python -split " "
    & $launcher[0] $launcher[1..($launcher.Length - 1)] -m venv $validation
    if ($LASTEXITCODE -ne 0) { throw "Could not create validation environment" }
    $pythonExe = Join-Path $validation "Scripts\python.exe"
    Invoke-Python $pythonExe @("-m", "pip", "install", "--upgrade", "pip", "setuptools>=83", ".[test]", "-r", "requirements-docs.txt", "cyclonedx-bom")
    Invoke-Python $pythonExe @("-m", "ruff", "check", "src", "tests")
    Invoke-Python $pythonExe @("-m", "ruff", "format", "--check", "src", "tests")
    Invoke-Python $pythonExe @("-m", "mypy")
    Invoke-Python $pythonExe @("-m", "coverage", "run", "-m", "pytest", "tests", "-q")
    Invoke-Python $pythonExe @("-m", "coverage", "json")
    Invoke-Python $pythonExe @("scripts/check_coverage.py")
    Invoke-Python $pythonExe @("-m", "coverage", "report")
    Invoke-Python $pythonExe @("-m", "mkdocs", "build", "--strict")
    Invoke-Python $pythonExe @("-m", "pip_audit", "--local", "--progress-spinner", "off")
    Invoke-Python $pythonExe @("-m", "build")
    Invoke-Python $pythonExe @("-m", "twine", "check", "dist/*")

    & $launcher[0] $launcher[1..($launcher.Length - 1)] -m venv $wheelValidation
    if ($LASTEXITCODE -ne 0) { throw "Could not create wheel environment" }
    $wheelPython = Join-Path $wheelValidation "Scripts\python.exe"
    $wheel = (Get-ChildItem -LiteralPath $distribution -Filter "*.whl" -File).FullName
    Invoke-Python $wheelPython @("-m", "pip", "install", $wheel, "pytest")
    Invoke-Python $wheelPython @("-m", "pip", "check")
    Push-Location $wheelValidation
    try {
        Invoke-Python $wheelPython @("-c", "import pathlib,vllm_optimizer; assert 'site-packages' in str(pathlib.Path(vllm_optimizer.__file__).resolve())")
        Invoke-Python $wheelPython @("-m", "pytest", (Join-Path $repository "tests"), "-q", "--import-mode=importlib")
    } finally { Pop-Location }
} finally { Pop-Location }
