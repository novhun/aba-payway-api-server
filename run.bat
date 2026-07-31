@echo off
set VENV_DIR=venv
set REQ_FILE=requirements.txt

:menu
cls
echo ==========================================================================
echo   Python VENV ^& FastAPI/Uvicorn Manager (CMD)
echo ==========================================================================
echo 1. Create venv -^> use venv
echo 2. Use venv -^> install pip from requirements.txt
echo 3. Use venv -^> install pip from requirements.txt -^> run uvicorn
echo 4. Run only: uvicorn main:app --host 0.0.0.0 --port 8001
echo 5. Install pip from requirements.txt -^> run uvicorn
echo 0. Exit
echo ==========================================================================
set /p choice="Enter your choice [0-5]: "

if "%choice%"=="1" goto option1
if "%choice%"=="2" goto option2
if "%choice%"=="3" goto option3
if "%choice%"=="4" goto option4
if "%choice%"=="5" goto option5
if "%choice%"=="0" goto exit

echo Invalid choice. Please try again.
pause
goto menu

:activate_venv
if exist "%VENV_DIR%\Scripts\activate.bat" (
    call "%VENV_DIR%\Scripts\activate.bat"
    echo Activated virtual environment (%VENV_DIR%).
) else (
    echo Error: '%VENV_DIR%' does not exist. Please run option 1 first.
)
exit /b

:install_reqs
if exist "%REQ_FILE%" (
    echo Installing dependencies from %REQ_FILE%...
    pip install -r "%REQ_FILE%"
) else (
    echo Warning: %REQ_FILE% not found!
)
exit /b

:option1
echo Creating virtual environment...
python -m venv %VENV_DIR%
call %VENV_DIR%\Scripts\activate.bat
echo Virtual environment created and activated.
pause
goto menu

:option2
call :activate_venv
call :install_reqs
pause
goto menu

:option3
call :activate_venv
call :install_reqs
echo Starting server...
uvicorn main:app --host 0.0.0.0 --port 8001
pause
goto menu

:option4
if exist "%VENV_DIR%\Scripts\activate.bat" (
    call "%VENV_DIR%\Scripts\activate.bat"
)
echo Starting server...
uvicorn main:app --host 0.0.0.0 --port 8001
pause
goto menu

:option5
call :install_reqs
echo Starting server...
uvicorn main:app --host 0.0.0.0 --port 8001
pause
goto menu

:exit
echo Exiting...
exit /b 0