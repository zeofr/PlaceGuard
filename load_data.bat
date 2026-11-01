@echo off
echo Loading PlaceGuard data...
set PYTHONPATH=%~dp0
python data\load_data.py
pause
