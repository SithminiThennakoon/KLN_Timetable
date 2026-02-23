<#
Simple script to start backend and frontend in separate PowerShell windows.
Usage: execute this script from the workspace root.
#>

$root = Split-Path -Path $MyInvocation.MyCommand.Definition -Parent

# start backend
Start-Process powershell -ArgumentList "-NoExit -Command `"cd '$root\backend'; `nif (-not (Test-Path .venv)) { python -m venv .venv }; `n.\.venv\Scripts\Activate.ps1; pip install fastapi uvicorn sqlalchemy pymysql python-dotenv; uvicorn app.main:app --reload --port 8000`"" -WindowStyle Normal

# start frontend (assumes package.json exists or user will run npm init)
Start-Process powershell -ArgumentList "-NoExit -Command `"cd '$root\frontend'; npm install; npm start`"" -WindowStyle Normal
