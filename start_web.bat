@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo 正在创建虚拟环境...
  py -3 -m venv .venv
  if errorlevel 1 python -m venv .venv
)
.venv\Scripts\python.exe -c "import gradio, fastmcp, langchain" 1>nul 2>nul
if errorlevel 1 (
  echo 正在安装依赖，第一次会久一点...
  .venv\Scripts\python.exe -m pip install -r requirements.txt
)
echo 打开浏览器访问 http://127.0.0.1:7860
.venv\Scripts\python.exe app.py
pause
