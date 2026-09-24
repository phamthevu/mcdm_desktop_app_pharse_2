@echo off
setlocal
cd /d %~dp0\..
python -m pip install -r requirements.txt
python -m pip install "pyinstaller>=6,<7"
python -m compileall -q .
if errorlevel 1 exit /b 1
python tests\stress_v47.py
python tests\test_v48_release.py
if errorlevel 1 exit /b 1
pyinstaller --noconfirm --clean packaging\research_studio.spec
if errorlevel 1 exit /b 1
echo.
echo Build complete: dist\ResearchStudio.exe
