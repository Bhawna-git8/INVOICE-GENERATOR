@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
where python >nul 2>&1 || (echo Python is missing. Install 3.10+ from python.org, tick "Add to PATH", then rerun. & pause & exit /b 1)
where ollama >nul 2>&1 || (echo Ollama is missing. Install it from https://ollama.com/download then rerun. & pause & exit /b 1)
if not exist .venv\Scripts\activate.bat python -m venv .venv
call .venv\Scripts\activate.bat
echo Installing Python packages (first run only)...
pip install -q -r requirements.txt || (echo pip install failed & pause & exit /b 1)
if "%OLLAMA_MODEL%"=="" set OLLAMA_MODEL=qwen2.5:7b
curl -s http://localhost:11434 >nul 2>&1 || start "" /min ollama serve
timeout /t 3 >nul
ollama list | findstr /i /c:"%OLLAMA_MODEL%" >nul || (echo Downloading %OLLAMA_MODEL% ... about 4.7 GB, one time only & ollama pull %OLLAMA_MODEL%)
echo.
echo   1 = Streamlit UI
echo   2 = Gradio UI
set /p UI=Choose UI [1/2]: 
if "%UI%"=="2" (python app_gradio.py) else (streamlit run app_streamlit.py)
pause
