# Установка всего необходимого на Windows (PowerShell):
#   .\scripts\setup.ps1            — Python-окружение, модель spaCy, пакеты сайта
#   .\scripts\setup.ps1 -Neural    — дополнительно LaBSE (sentence-transformers, ~2 ГБ)
param([switch]$Neural)

$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw 'Не найден запуск Python (py). Установите Python 3.11 с python.org и отметьте "Add python.exe to PATH".'
}

Write-Host '1/4 Создаю виртуальное окружение .venv (Python 3.11)…'
py -3.11 -m venv .venv
$python = Join-Path (Get-Location) '.venv\Scripts\python.exe'

Write-Host '2/4 Устанавливаю зависимости pipeline…'
& $python -m pip install --upgrade pip
& $python -m pip install -r pipeline\requirements-dev.txt

Write-Host '3/4 Скачиваю модель spaCy для английского…'
& $python -m spacy download en_core_web_sm
if ($Neural) {
    Write-Host '    + LaBSE (sentence-transformers)…'
    & $python -m pip install -r pipeline\requirements-neural.txt
}

Write-Host '4/4 Устанавливаю пакеты сайта…'
if (Get-Command npm -ErrorAction SilentlyContinue) {
    Push-Location web
    npm ci
    Pop-Location
} else {
    Write-Warning 'Node.js не найден: сайт можно будет запустить после установки Node.js 22 LTS (nodejs.org).'
}

Write-Host ''
Write-Host 'Готово. Дальше:'
Write-Host '  .venv\Scripts\Activate.ps1'
Write-Host '  python -m pipeline build'
Write-Host '  cd web; npm run dev'
