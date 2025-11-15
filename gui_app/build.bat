@echo off
echo ========================================
echo   JAIson GUI - Build do Executavel
echo ========================================
echo.

powershell -ExecutionPolicy Bypass -File "%~dp0build.ps1"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Build concluido! Verifique a pasta 'dist'
    pause
) else (
    echo.
    echo Erro no build. Verifique as mensagens acima.
    pause
    exit /b 1
)










