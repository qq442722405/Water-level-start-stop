# 水位数字自动控制

Windows 水位数字 OCR 自动控制软件。

## 本版本重点

- **不使用单文件 EXE**
- 使用 PyInstaller **目录版（onedir）**
- 内置 ddddocr + ONNX Runtime
- 显式收集 `onnxruntime` 的 DLL、Python 模块和运行文件
- 固定 `onnxruntime==1.19.2`，降低在线打包环境版本变化造成的 DLL 问题
- 使用 `app.ico` 作为程序图标
- GitHub Actions 自动打包并生成 ZIP

## 为什么改成目录版

之前单文件版本出现：

`ImportError: DLL load failed while importing onnxruntime_pybind11_state: 动态链接库(DLL)初始化例程失败`

单文件模式会先把 DLL 解压到临时目录，再启动程序。OCR 的 ONNX Runtime 对这种启动方式更容易出现 DLL 初始化/依赖加载问题。

因此本版本改成目录版：

```text
dist/
└── 水位数字自动控制/
    ├── 水位数字自动控制.exe
    ├── app.ico
    ├── ddddocr/
    ├── onnxruntime/
    ├── onnxruntime_providers_shared.dll
    └── 其他运行依赖
```

不要单独拿 EXE 文件运行，要**整个“水位数字自动控制”文件夹一起使用**。

## 使用

1. 框选水位数字区域。
2. 设置高水位阈值，例如 `2.5`。
3. 设置低水位阈值，例如 `2.0`。
4. 设置检测间隔，例如 `1` 秒。
5. 抓取高水位控制按钮坐标。
6. 抓取低水位控制按钮坐标。
7. 保存配置。
8. 开始监控。

逻辑：

- `水位 > 高水位阈值` → 点击高水位控制点
- `水位 < 低水位阈值` → 点击低水位控制点
- 中间区域不动作
- 检测间隔控制 OCR 检测和自动动作频率
- 最小点击间隔用于额外防止快速重复点击

## GitHub 在线打包

上传整个工程到 GitHub：

`Actions → Windows EXE Build → Run workflow`

完成后下载：

`水位数字自动控制-Windows`

下载 ZIP 后解压，进入：

`水位数字自动控制\水位数字自动控制.exe`

运行即可。

## 图标

`app.ico` 是软件 LOGO 的 Windows 图标版本。
