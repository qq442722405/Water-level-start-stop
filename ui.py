from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QLabel, QPushButton, QDoubleSpinBox, QSpinBox,
    QGridLayout, QVBoxLayout, QHBoxLayout, QGroupBox, QTextEdit,
    QMessageBox, QCheckBox, QDialog, QComboBox, QDialogButtonBox,
    QFormLayout, QSlider, QFrame, QSizePolicy
)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QIcon, QPixmap, QImage
from screen_tools import RegionSelector, PointPicker, screenshot_region
from settings import load_settings, save_settings, DEFAULTS
from ocr_engine import NumberOCR
from monitor import MonitorThread
import cv2
import numpy as np


class CleanDoubleSpinBox(QDoubleSpinBox):
    def textFromValue(self, val):
        s = f"{val:.3f}".rstrip("0").rstrip(".")
        return s if s else "0"


class OCRAdjustDialog(QDialog):
    """OCR 详细调整窗口：现场截图、预处理预览、实时测试。"""
    def __init__(self, ocr, config, region_getter, parent=None):
        super().__init__(parent)
        self.ocr = ocr
        self.base_config = config.copy()
        self.region_getter = region_getter
        self.setWindowTitle("识别调整 - OCR 详细参数")
        self.resize(900, 650)
        self.setModal(True)
        self.build_ui()
        self.load_values(self.base_config)
        self.test_ocr()

    def make_double(self, value, lo, hi, decimals=2, step=0.1):
        w = CleanDoubleSpinBox()
        w.setRange(lo, hi)
        w.setDecimals(decimals)
        w.setSingleStep(step)
        w.setValue(float(value))
        return w

    def make_int(self, value, lo, hi, step=1):
        w = QSpinBox()
        w.setRange(lo, hi)
        w.setSingleStep(step)
        w.setValue(int(value))
        return w

    def build_ui(self):
        self.setStyleSheet("""
        QDialog { background:#f5f7fa; }
        QWidget { font-family:'Microsoft YaHei'; font-size:13px; color:#263238; }
        QGroupBox { background:white; border:1px solid #dfe5eb; border-radius:10px; margin-top:10px; padding:12px; font-weight:bold; }
        QGroupBox::title { subcontrol-origin:margin; left:12px; padding:0 5px; color:#1f6f8b; }
        QSpinBox, QDoubleSpinBox, QComboBox { background:white; border:1px solid #cbd5df; border-radius:6px; padding:6px; min-height:22px; }
        QPushButton { background:white; border:1px solid #cbd5df; border-radius:7px; padding:7px 14px; }
        QPushButton:hover { background:#eef8fb; border-color:#1fa3c8; }
        QPushButton#testBtn { background:#1769aa; color:white; border:none; font-weight:bold; }
        QLabel#result { font-size:24px; font-weight:bold; color:#087f9c; }
        QLabel#hint { color:#64748b; font-size:12px; }
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)

        top = QHBoxLayout()
        title = QLabel("识别调整")
        title.setStyleSheet("font-size:22px;font-weight:bold;color:#183642;")
        top.addWidget(title)
        top.addStretch()
        self.result = QLabel("识别结果：--")
        self.result.setObjectName("result")
        top.addWidget(self.result)
        root.addLayout(top)

        body = QHBoxLayout()
        left = QGroupBox("识别详细参数")
        form = QFormLayout()
        self.scale = self.make_int(3, 1, 6)
        self.mode = QComboBox()
        self.mode.addItems(["原图+二值化", "原图", "灰度", "固定阈值", "自适应"])
        self.threshold = self.make_int(160, 0, 255)
        self.blur = self.make_int(3, 1, 15, 2)
        self.contrast = self.make_double(1.0, 0.2, 3.0, 2, 0.1)
        self.brightness = self.make_int(0, -100, 100, 5)
        self.sharpen = self.make_int(0, 0, 3)
        self.invert = QCheckBox("黑白反转")

        form.addRow("放大倍数", self.scale)
        form.addRow("预处理模式", self.mode)
        form.addRow("固定阈值", self.threshold)
        form.addRow("降噪/模糊", self.blur)
        form.addRow("对比度", self.contrast)
        form.addRow("亮度", self.brightness)
        form.addRow("锐化", self.sharpen)
        form.addRow("反转", self.invert)
        hint = QLabel("建议先框选只包含水位数字和小数点的区域，再逐项测试。\n固定阈值适合背景稳定；自适应适合亮度不均匀。")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        form.addRow(hint)
        left.setLayout(form)
        body.addWidget(left, 0)

        right = QVBoxLayout()
        preview_box = QGroupBox("预处理效果")
        pv = QHBoxLayout()
        self.raw_preview = QLabel("原图")
        self.processed_preview = QLabel("调整后")
        for w in (self.raw_preview, self.processed_preview):
            w.setAlignment(Qt.AlignCenter)
            w.setMinimumSize(260, 180)
            w.setStyleSheet("background:#eef1f4;border:1px solid #d5dce3;border-radius:6px;color:#7b8794;")
            w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        pv.addWidget(self.raw_preview)
        pv.addWidget(self.processed_preview)
        preview_box.setLayout(pv)
        right.addWidget(preview_box, 1)

        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setMaximumHeight(115)
        right.addWidget(self.detail)

        test = QPushButton("重新截图并测试识别")
        test.setObjectName("testBtn")
        test.clicked.connect(self.test_ocr)
        right.addWidget(test)
        body.addLayout(right, 1)
        root.addLayout(body, 1)

        bottom = QHBoxLayout()
        bottom.addStretch()
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        buttons.button(QDialogButtonBox.Ok).setText("应用参数")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        bottom.addWidget(buttons)
        root.addLayout(bottom)

    def load_values(self, cfg):
        self.scale.setValue(int(cfg.get("ocr_scale", 3)))
        self.mode.setCurrentText(cfg.get("ocr_mode", "原图+二值化"))
        self.threshold.setValue(int(cfg.get("ocr_threshold", 160)))
        self.blur.setValue(int(cfg.get("ocr_blur", 3)))
        self.contrast.setValue(float(cfg.get("ocr_contrast", 1.0)))
        self.brightness.setValue(int(cfg.get("ocr_brightness", 0)))
        self.sharpen.setValue(int(cfg.get("ocr_sharpen", 0)))
        self.invert.setChecked(bool(cfg.get("ocr_invert", False)))

    def collect(self):
        cfg = self.base_config.copy()
        cfg["ocr_scale"] = self.scale.value()
        cfg["ocr_mode"] = self.mode.currentText()
        cfg["ocr_threshold"] = self.threshold.value()
        cfg["ocr_blur"] = self.blur.value()
        cfg["ocr_contrast"] = self.contrast.value()
        cfg["ocr_brightness"] = self.brightness.value()
        cfg["ocr_sharpen"] = self.sharpen.value()
        cfg["ocr_invert"] = self.invert.isChecked()
        return cfg

    def set_preview(self, label, image, max_w=400, max_h=260):
        if image is None or image.size == 0:
            label.setText("无图像")
            return
        if image.ndim == 2:
            qimg = QImage(image.data, image.shape[1], image.shape[0], image.strides[0], QImage.Format_Grayscale8).copy()
        else:
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            qimg = QImage(rgb.data, rgb.shape[1], rgb.shape[0], rgb.strides[0], QImage.Format_RGB888).copy()
        pix = QPixmap.fromImage(qimg)
        label.setPixmap(pix.scaled(max_w, max_h, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def test_ocr(self):
        try:
            rect = self.region_getter()
            image = screenshot_region(rect)
            cfg = self.collect()
            processed = self.ocr.preprocess(image, cfg)
            value, detail = self.ocr.recognize(image, cfg, return_detail=True)
            self.set_preview(self.raw_preview, image)
            self.set_preview(self.processed_preview, processed)
            self.result.setText(f"识别结果：{value:g}" if value is not None else "识别结果：无法识别")
            lines = ["识别明细："]
            for item in detail:
                lines.append(f"{item['name']}：原始={item['raw']}  数值={item['value']}")
            self.detail.setPlainText("\n".join(lines))
        except Exception as e:
            self.result.setText("识别结果：测试失败")
            self.detail.setPlainText(f"错误：{e}")

    def get_config(self):
        return self.collect()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = load_settings()
        self.ocr = NumberOCR(self.cfg)
        self.monitor = None
        self.selector = None
        self.point_picker = None
        self.current_value = None
        self.setWindowTitle("水位数字自动控制")
        self.setWindowIcon(QIcon("app.ico"))
        self.resize(int(self.cfg.get("window_width", 900)), int(self.cfg.get("window_height", 720)))
        self.build_ui()

        self.preview_timer = QTimer(self)
        self.preview_timer.timeout.connect(self.preview_ocr)
        self.preview_timer.start(700)

    def make_double(self, value, lo=-999999, hi=999999, decimals=3, step=0.1):
        w = CleanDoubleSpinBox()
        w.setRange(lo, hi)
        w.setDecimals(decimals)
        w.setSingleStep(step)
        w.setValue(float(value))
        return w

    def make_int(self, value, lo=1, hi=999999):
        w = QSpinBox()
        w.setRange(lo, hi)
        w.setValue(int(value))
        return w

    def build_ui(self):
        self.setStyleSheet("""
        QMainWindow { background: #f5f7fa; }
        QWidget { font-family: 'Microsoft YaHei'; font-size: 14px; color: #263238; }
        QGroupBox { background: white; border: 1px solid #dfe5eb; border-radius: 10px; margin-top: 10px; padding: 12px; font-weight: bold; }
        QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; color: #1f6f8b; }
        QDoubleSpinBox, QSpinBox, QComboBox { background: white; border: 1px solid #cbd5df; border-radius: 6px; padding: 7px 8px; min-height: 22px; }
        QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus { border: 1px solid #1fa3c8; }
        QPushButton { background: #ffffff; border: 1px solid #cbd5df; border-radius: 7px; padding: 8px 14px; }
        QPushButton:hover { background: #eef8fb; border-color: #1fa3c8; }
        QPushButton#startBtn { background: #138a5b; color: white; border: none; font-weight: bold; }
        QPushButton#stopBtn { background: #d9534f; color: white; border: none; font-weight: bold; }
        QPushButton#saveBtn { background: #1769aa; color: white; border: none; font-weight: bold; }
        QPushButton#ocrAdjustBtn { background: #6f42c1; color: white; border: none; font-weight: bold; }
        QLabel#title { font-size: 26px; font-weight: bold; color: #183642; }
        QLabel#value { font-size: 34px; font-weight: bold; color: #087f9c; }
        QLabel#status { color: #64748b; }
        QTextEdit { background: #fbfcfd; border: 1px solid #dfe5eb; border-radius: 7px; }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("水位数字自动控制")
        title.setObjectName("title")
        header.addWidget(title)
        header.addStretch()
        self.run_badge = QLabel("● 未运行")
        self.run_badge.setStyleSheet("color:#7b8794;font-weight:bold;")
        header.addWidget(self.run_badge)
        root.addLayout(header)

        desc = QLabel("实时识别水位数字，并根据高、低水位阈值自动执行指定操作。检测间隔与操作间隔独立设置。")
        desc.setStyleSheet("color:#64748b;")
        root.addWidget(desc)

        param_box = QGroupBox("运行参数")
        pg = QGridLayout()
        pg.setHorizontalSpacing(12)
        pg.setVerticalSpacing(8)

        self.high = self.make_double(self.cfg["high_threshold"], -9999, 9999, 3, 0.1)
        self.low = self.make_double(self.cfg["low_threshold"], -9999, 9999, 3, 0.1)
        self.detection_interval = self.make_double(self.cfg.get("detection_interval", 1.0), 0.05, 3600, 2, 0.1)
        self.operation_interval = self.make_double(self.cfg.get("operation_interval", 3.0), 0.05, 3600, 2, 0.1)
        self.safety_operator = QComboBox()
        self.safety_operator.addItems([">", ">=", "<"])
        self.safety_operator.setCurrentText(self.cfg.get("safety_operator", ">"))
        self.safety_value = self.make_double(self.cfg.get("safety_value", 20.0), 0.01, 999999, 3, 0.5)
        self.clicks = self.make_int(self.cfg["clicks_per_action"], 1, 20)

        pg.addWidget(QLabel("高水位阈值（>）"), 0, 0)
        pg.addWidget(self.high, 0, 1)
        pg.addWidget(QLabel("低水位阈值（<）"), 0, 2)
        pg.addWidget(self.low, 0, 3)
        pg.addWidget(QLabel("检测间隔（秒）"), 1, 0)
        pg.addWidget(self.detection_interval, 1, 1)
        pg.addWidget(QLabel("操作间隔（秒）"), 1, 2)
        pg.addWidget(self.operation_interval, 1, 3)
        pg.addWidget(QLabel("识别安全"), 2, 0)
        safety_row = QHBoxLayout()
        safety_row.addWidget(self.safety_operator)
        safety_row.addWidget(self.safety_value)
        pg.addLayout(safety_row, 2, 1)
        safety_hint = QLabel("满足此条件的识别结果禁止自动操作")
        safety_hint.setStyleSheet("color:#9a6a00;font-size:12px;")
        pg.addWidget(safety_hint, 2, 2, 1, 2)
        pg.addWidget(QLabel("每次操作点击次数"), 3, 0)
        pg.addWidget(self.clicks, 3, 1)
        param_box.setLayout(pg)
        root.addWidget(param_box)

        ocr_box = QGroupBox("① 水位数字识别")
        og = QHBoxLayout()
        self.ocr_info = QLabel(self.region_text())
        self.ocr_info.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        btn_region = QPushButton("框选识别区域")
        btn_region.clicked.connect(self.select_region)
        btn_adjust = QPushButton("识别调整")
        btn_adjust.setObjectName("ocrAdjustBtn")
        btn_adjust.clicked.connect(self.open_ocr_adjust)
        og.addWidget(self.ocr_info)
        og.addWidget(btn_region)
        og.addWidget(btn_adjust)
        ocr_box.setLayout(og)
        root.addWidget(ocr_box)

        action_box = QGroupBox("② 自动操作点")
        ag = QGridLayout()
        self.high_point = QLabel(self.point_text("high"))
        self.low_point = QLabel(self.point_text("low"))
        bh = QPushButton("抓取高水位操作点")
        bl = QPushButton("抓取低水位操作点")
        bh.clicked.connect(lambda: self.capture_point("high"))
        bl.clicked.connect(lambda: self.capture_point("low"))
        ag.addWidget(self.high_point, 0, 0)
        ag.addWidget(bh, 0, 1)
        ag.addWidget(self.low_point, 1, 0)
        ag.addWidget(bl, 1, 1)
        note = QLabel("点击抓取后立即出现全屏十字光标，直接点击目标位置即可。右键取消。")
        note.setStyleSheet("color:#64748b;font-size:12px;")
        ag.addWidget(note, 2, 0, 1, 2)
        action_box.setLayout(ag)
        root.addWidget(action_box)

        status_box = QGroupBox("③ 实时状态")
        sv = QVBoxLayout()
        self.value_label = QLabel("当前水位：--")
        self.value_label.setObjectName("value")
        self.status_label = QLabel("状态：未启动")
        self.status_label.setObjectName("status")
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(100)
        self.log.setMaximumHeight(135)
        sv.addWidget(self.value_label)
        sv.addWidget(self.status_label)
        sv.addWidget(self.log)
        status_box.setLayout(sv)
        root.addWidget(status_box, 1)

        bottom = QHBoxLayout()
        self.enable = QCheckBox("允许自动操作")
        self.enable.setChecked(bool(self.cfg.get("click_enabled", True)))
        bottom.addWidget(self.enable)
        bottom.addStretch()

        save = QPushButton("保存配置")
        save.setObjectName("saveBtn")
        save.clicked.connect(self.save)
        start = QPushButton("开始监控")
        start.setObjectName("startBtn")
        start.clicked.connect(self.start_monitor)
        stop = QPushButton("停止监控")
        stop.setObjectName("stopBtn")
        stop.clicked.connect(self.stop_monitor)
        reset = QPushButton("恢复默认")
        reset.clicked.connect(self.reset)

        bottom.addWidget(save)
        bottom.addWidget(start)
        bottom.addWidget(stop)
        bottom.addWidget(reset)
        root.addLayout(bottom)

        tip = QLabel("逻辑：水位 > 高阈值执行高水位点；水位 < 低阈值执行低水位点；中间区域不操作。识别安全拦截优先级最高。")
        tip.setStyleSheet("color:#64748b;font-size:12px;")
        root.addWidget(tip)

    def region_text(self):
        return f"X={self.cfg['ocr_left']}  Y={self.cfg['ocr_top']}  W={self.cfg['ocr_width']}  H={self.cfg['ocr_height']}"

    def point_text(self, kind):
        label = "高水位" if kind == "high" else "低水位"
        return f"{label}操作点：X={self.cfg[f'{kind}_x']}  Y={self.cfg[f'{kind}_y']}"

    def select_region(self):
        self.selector = RegionSelector()
        self.selector.selected.connect(self.region_selected)
        self.selector.show()

    def region_selected(self, r):
        self.cfg["ocr_left"] = r.x()
        self.cfg["ocr_top"] = r.y()
        self.cfg["ocr_width"] = r.width()
        self.cfg["ocr_height"] = r.height()
        self.ocr_info.setText(self.region_text())
        self.log.append("✓ 已设置水位数字识别区域")

    def capture_point(self, kind):
        self.pending_point = kind
        title = "抓取高水位操作点：直接点击需要操作的位置" if kind == "high" else "抓取低水位操作点：直接点击需要操作的位置"
        self.point_picker = PointPicker(title)
        self.point_picker.picked.connect(self.point_picked)
        self.point_picker.cancelled.connect(lambda: self.point_picker.deleteLater())
        self.point_picker.show()
        self.point_picker.raise_()
        self.point_picker.activateWindow()

    def point_picked(self, x, y):
        kind = self.pending_point
        self.cfg[f"{kind}_x"] = x
        self.cfg[f"{kind}_y"] = y
        if kind == "high":
            self.high_point.setText(self.point_text("high"))
        else:
            self.low_point.setText(self.point_text("low"))
        self.log.append(f"✓ 已抓取{'高水位' if kind == 'high' else '低水位'}操作点：X={x} Y={y}")
        self.point_picker = None

    def current_region(self):
        class R:
            def x(s): return self.cfg["ocr_left"]
            def y(s): return self.cfg["ocr_top"]
            def width(s): return self.cfg["ocr_width"]
            def height(s): return self.cfg["ocr_height"]
        return R()

    def open_ocr_adjust(self):
        self.read_config()
        dlg = OCRAdjustDialog(self.ocr, self.cfg, self.current_region, self)
        if dlg.exec_() == QDialog.Accepted:
            self.cfg.update(dlg.get_config())
            self.ocr.update_config(self.cfg)
            self.log.append("✓ OCR 识别参数已应用；点击“保存配置”后永久保存")

    def preview_ocr(self):
        if self.monitor and self.monitor.isRunning():
            return
        try:
            value = self.ocr.recognize(screenshot_region(self.current_region()), self.cfg)
            if value is not None:
                self.value_label.setText(f"当前水位：{value:g}")
        except Exception:
            pass

    def read_config(self):
        self.cfg["high_threshold"] = self.high.value()
        self.cfg["low_threshold"] = self.low.value()
        self.cfg["detection_interval"] = self.detection_interval.value()
        self.cfg["operation_interval"] = self.operation_interval.value()
        self.cfg["safety_operator"] = self.safety_operator.currentText()
        self.cfg["safety_value"] = self.safety_value.value()
        self.cfg["clicks_per_action"] = self.clicks.value()
        self.cfg["click_enabled"] = self.enable.isChecked()
        self.cfg["window_width"] = self.width()
        self.cfg["window_height"] = self.height()
        self.ocr.update_config(self.cfg)

    def save(self):
        self.read_config()
        save_settings(self.cfg)
        self.log.append(f"✓ 配置已保存（检测 {self.detection_interval.value():g}s / 操作 {self.operation_interval.value():g}s / 窗口 {self.width()}×{self.height()}）")

    def start_monitor(self):
        if self.monitor and self.monitor.isRunning():
            return
        self.read_config()
        if self.cfg["low_threshold"] >= self.cfg["high_threshold"]:
            QMessageBox.warning(self, "参数错误", "低水位阈值必须小于高水位阈值。")
            return
        if self.cfg["detection_interval"] <= 0 or self.cfg["operation_interval"] <= 0:
            QMessageBox.warning(self, "参数错误", "检测间隔和操作间隔必须大于 0。")
            return
        save_settings(self.cfg)
        self.monitor = MonitorThread(self.ocr, self.cfg)
        self.monitor.value_signal.connect(self.on_value)
        self.monitor.status_signal.connect(self.status_label.setText)
        self.monitor.action_signal.connect(lambda s: self.log.append(s))
        self.monitor.start()
        self.run_badge.setText("● 运行中")
        self.run_badge.setStyleSheet("color:#138a5b;font-weight:bold;")
        self.log.append("▶ 监控已启动")

    def stop_monitor(self):
        if self.monitor:
            self.monitor.stop()
            self.monitor.wait(2000)
            self.monitor = None
        self.status_label.setText("状态：已停止")
        self.run_badge.setText("● 未运行")
        self.run_badge.setStyleSheet("color:#7b8794;font-weight:bold;")
        self.log.append("■ 监控已停止")

    def on_value(self, value):
        if value is None:
            return
        self.current_value = value
        self.value_label.setText(f"当前水位：{value:g}")

    def reset(self):
        self.cfg = DEFAULTS.copy()
        self.high.setValue(self.cfg["high_threshold"])
        self.low.setValue(self.cfg["low_threshold"])
        self.detection_interval.setValue(self.cfg["detection_interval"])
        self.operation_interval.setValue(self.cfg["operation_interval"])
        self.safety_operator.setCurrentText(self.cfg["safety_operator"])
        self.safety_value.setValue(self.cfg["safety_value"])
        self.clicks.setValue(self.cfg["clicks_per_action"])
        self.enable.setChecked(True)
        self.ocr_info.setText(self.region_text())
        self.high_point.setText(self.point_text("high"))
        self.low_point.setText(self.point_text("low"))
        self.ocr.update_config(self.cfg)
        self.log.append("↺ 已恢复默认参数（未自动保存）")

    def closeEvent(self, e):
        self.read_config()
        save_settings(self.cfg)
        self.stop_monitor()
        e.accept()
