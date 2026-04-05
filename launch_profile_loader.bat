@echo off
pip install pywebview >nul 2>&1
python "%~dp0app\profile_selector.py"
