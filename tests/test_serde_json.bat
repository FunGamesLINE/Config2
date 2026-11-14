@echo off
cd /d "%~dp0.."
py src\main.py -c tests\serde_json.yaml
pause