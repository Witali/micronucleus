@echo off
py -3 "%~dp0controller.py"
if errorlevel 1 pause
