@echo off
echo ======================================================================
echo    BUILDING STANDALONE WINDOWS EXECUTABLE FOR CDC PIPELINE MANAGER
echo ======================================================================

set PYTHON_CMD=python
where %PYTHON_CMD% >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python not found in system PATH.
    pause
    exit /b 1
)

echo [*] Installing / Verifying requirements...
%PYTHON_CMD% -m pip install -r requirements.txt

echo [*] Compiling Windows Executable using PyInstaller...
%PYTHON_CMD% -m PyInstaller --clean -y cdc_pipeline.spec

if %ERRORLEVEL% neq 0 (
    echo [ERROR] PyInstaller compilation failed!
    pause
    exit /b %ERRORLEVEL%
)

echo [*] Preparing distribution directories...
if not exist "dist\CDC_Data_Pipeline_Manager\data\input" mkdir "dist\CDC_Data_Pipeline_Manager\data\input"
if not exist "dist\CDC_Data_Pipeline_Manager\data\output" mkdir "dist\CDC_Data_Pipeline_Manager\data\output"
if not exist "dist\CDC_Data_Pipeline_Manager\data\quarantine" mkdir "dist\CDC_Data_Pipeline_Manager\data\quarantine"
if not exist "dist\CDC_Data_Pipeline_Manager\database" mkdir "dist\CDC_Data_Pipeline_Manager\database"
if not exist "dist\CDC_Data_Pipeline_Manager\reports" mkdir "dist\CDC_Data_Pipeline_Manager\reports"
if not exist "dist\CDC_Data_Pipeline_Manager\logs" mkdir "dist\CDC_Data_Pipeline_Manager\logs"

echo [*] Copying sample datasets...
if exist "data\input\customer_events.csv" (
    copy "data\input\customer_events.csv" "dist\CDC_Data_Pipeline_Manager\data\input\" >nul
)
if exist "data\input\customer_events.json" (
    copy "data\input\customer_events.json" "dist\CDC_Data_Pipeline_Manager\data\input\" >nul
)

echo ======================================================================
echo [SUCCESS] Windows Executable built successfully!
echo Executable location:
echo dist\CDC_Data_Pipeline_Manager\CDC_Data_Pipeline_Manager.exe
echo ======================================================================
