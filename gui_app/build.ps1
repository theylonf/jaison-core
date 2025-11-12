param(
    [string]$PythonExe = ""
)

# Try to find conda first, then fallback to venv
if ([string]::IsNullOrEmpty($PythonExe)) {
    $condaExe = Get-Command conda -ErrorAction SilentlyContinue
    if ($condaExe) {
        Write-Host "Usando ambiente conda 'jaison-core'..." -ForegroundColor Cyan
        $PythonExe = "conda"
        $useConda = $true
    } else {
        $venvPython = "..\.venv\Scripts\python.exe"
        if (Test-Path $venvPython) {
            Write-Host "Usando venv local..." -ForegroundColor Cyan
            $PythonExe = $venvPython
            $useConda = $false
        } else {
            Write-Host "Erro: Conda ou venv nao encontrados!" -ForegroundColor Red
            Write-Host "Instale conda ou crie um venv primeiro." -ForegroundColor Yellow
            exit 1
        }
    }
}

# Install dependencies
Write-Host "Instalando dependencias..." -ForegroundColor Cyan
if ($useConda) {
    # Get conda environment path using conda info
    $envList = conda info --envs 2>$null
    $envLine = $envList | Select-String "jaison-core"
    
    if ($envLine) {
        # Parse the line: "jaison-core    C:\Users\...\envs\jaison-core"
        $parts = $envLine.Line -split '\s+', 2
        if ($parts.Length -ge 2) {
            $envPath = $parts[1].Trim()
            $PythonExe = Join-Path $envPath "python.exe"
        }
    }
    
    # Fallback: try common locations
    if (!(Test-Path $PythonExe)) {
        $possiblePaths = @(
            "$env:USERPROFILE\miniconda3\envs\jaison-core\python.exe",
            "$env:USERPROFILE\anaconda3\envs\jaison-core\python.exe",
            "$env:LOCALAPPDATA\Continuum\anaconda3\envs\jaison-core\python.exe"
        )
        foreach ($path in $possiblePaths) {
            if (Test-Path $path) {
                $PythonExe = $path
                break
            }
        }
    }
    
    if (!(Test-Path $PythonExe)) {
        Write-Host "Erro: Nao foi possivel encontrar o Python do ambiente jaison-core" -ForegroundColor Red
        Write-Host "Execute: conda activate jaison-core" -ForegroundColor Yellow
        exit 1
    }
    
    Write-Host "Usando Python: $PythonExe" -ForegroundColor Gray
    & $PythonExe -m pip install --upgrade pip -q
    & $PythonExe -m pip install -r requirements.txt pyinstaller -q
    $pythonCmd = $PythonExe
} else {
    & $PythonExe -m pip install --upgrade pip -q
    & $PythonExe -m pip install -r requirements.txt pyinstaller -q
    $pythonCmd = $PythonExe
}

# Build executable
Write-Host "Criando executavel..." -ForegroundColor Cyan
& $pythonCmd -m PyInstaller `
    --noconfirm `
    --onefile `
    --windowed `
    --name JAIsonGUI `
    --add-data "requirements.txt;." `
    --hidden-import sounddevice `
    --hidden-import numpy `
    --hidden-import requests `
    --hidden-import PySide6 `
    --collect-all sounddevice `
    --collect-all numpy `
    --clean `
    .\app.py

if (Test-Path "dist\JAIsonGUI.exe") {
    Write-Host ""
    Write-Host "Build finalizado com sucesso!" -ForegroundColor Green
    Write-Host "Executavel criado em: dist\JAIsonGUI.exe" -ForegroundColor Green
    Write-Host ""
    Write-Host "Voce pode executar o arquivo diretamente sem precisar do terminal!" -ForegroundColor Cyan
} else {
    Write-Host ""
    Write-Host "Erro ao criar executavel. Verifique os logs acima." -ForegroundColor Red
    exit 1
}


