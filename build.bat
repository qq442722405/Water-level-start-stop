@echo off
chcp 65001 >nul
python -m pip install --upgrade pip
pip install -r requirements.txt
pyinstaller --noconfirm --clean --onefile --windowed --name "水位数字自动控制" --collect-all ddddocr main.py
echo.
echo 打包完成：dist\水位数字自动控制.exe
pause
