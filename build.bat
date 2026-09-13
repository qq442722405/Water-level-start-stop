@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [1/3] 安装依赖...
python -m pip install --upgrade pip
pip install -r requirements.txt

echo [2/3] 清理旧打包...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist "水位数字自动控制.spec" del /q "水位数字自动控制.spec"

echo [3/3] 打包为目录版（不是单文件）...
pyinstaller --noconfirm --clean --windowed --name "水位数字自动控制" --icon=app.ico ^
  --collect-all ddddocr ^
  --collect-all onnxruntime ^
  --hidden-import=onnxruntime ^
  --hidden-import=onnxruntime.capi._pybind_state ^
  main.py

copy /y app.ico "dist\水位数字自动控制\app.ico" >nul

echo.
echo ==========================================
echo 打包完成！
echo 输出目录：
echo dist\水位数字自动控制\
echo 启动：
echo dist\水位数字自动控制\水位数字自动控制.exe
echo ==========================================
pause
