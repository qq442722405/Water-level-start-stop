from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QLabel, QPushButton, QDoubleSpinBox, QSpinBox,
    QGridLayout, QVBoxLayout, QHBoxLayout, QGroupBox, QTextEdit,
    QMessageBox, QCheckBox, QFrame, QSizePolicy
)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QIcon, QFont
from screen_tools import RegionSelector, PointPicker, screenshot_region
from settings import load_settings, save_settings, DEFAULTS
from ocr_engine import NumberOCR
from monitor import MonitorThread


class CleanDoubleSpinBox(QDoubleSpinBox):
    def textFromValue(self, val):
        s = f"{val:.3f}".rstrip("0").rstrip(".")
        return s if s else "0"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = load_settings()
        self.ocr = NumberOCR()
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
        QDoubleSpinBox, QSpinBox { background: white; border: 1px solid #cbd5df; border-radius: 6px; padding: 7px 8px; min-height: 22px; }
        QDoubleSpinBox:focus, QSpinBox:focus { border: 1px solid #1fa3c8; }
        QPushButton { background: #ffffff; border: 1px solid #cbd5df; border-radius: 7px; padding: 8px 14px; }
        QPushButton:hover { background: #eef8fb; border-color: #1fa3c8; }
        QPushButton#startBtn { background: #138a5b; color: white; border: none; font-weight: bold; }
        QPushButton#startBtn:hover { background: #0f774f; }
        QPushButton#stopBtn { background: #d9534f; color: white; border: none; font-weight: bold; }
        QPushButton#saveBtn { background: #1769aa; color: white; border: none; font-weight: bold; }
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

        desc = QLabel("实时识别水位数字，并根据高、低水位阈值自动执行指定点击操作。")
        desc.setStyleSheet("color:#64748b;")
        root.addWidget(desc)

        # 参数区
        param_box = QGroupBox("运行参数")
        pg = QGridLayout()
        pg.setHorizontalSpacing(12)
        pg.setVerticalSpacing(8)

        self.high = self.make_double(self.cfg["high_threshold"], -9999, 9999, 3, 0.1)
        self.low = self.make_double(self.cfg["low_threshold"], -9999, 9999, 3, 0.1)
        self.interval = self.make_double(self.cfg["interval"], 0.05, 3600, 2, 0.1)
        self.max_valid = self.make_double(self.cfg.get("max_valid_value", 20.0), 0.01, 999999, 3, 0.5)
        self.clicks = self.make_int(self.cfg["clicks_per_action"], 1, 20)

        pg.addWidget(QLabel("高水位阈值（>）"), 0, 0)
        pg.addWidget(self.high, 0, 1)
        pg.addWidget(QLabel("低水位阈值（<）"), 0, 2)
        pg.addWidget(self.low, 0, 3)
        pg.addWidget(QLabel("操作间隔（秒）"), 1, 0)
        pg.addWidget(self.interval, 1, 1)
        pg.addWidget(QLabel("识别安全上限（> 不点击）"), 1, 2)
        pg.addWidget(self.max_valid, 1, 3)
        pg.addWidget(QLabel("每次操作点击次数"), 2, 0)
        pg.addWidget(self.clicks, 2, 1)
        tip = QLabel("安全上限用于防止 OCR 识别错误，例如实际水位 2.5，却误识别成 25。")
        tip.setStyleSheet("color:#9a6a00;font-size:12px;")
        pg.addWidget(tip, 2, 2, 1, 2)
        param_box.setLayout(pg)
        root.addWidget(param_box)

        # 识别区
        ocr_box = QGroupBox("① 水位数字识别区域")
        og = QHBoxLayout()
        self.ocr_info = QLabel(self.region_text())
        self.ocr_info.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        btn_region = QPushButton("框选识别区域")
        btn_region.clicked.connect(self.select_region)
        og.addWidget(self.ocr_info)
        og.addWidget(btn_region)
        ocr_box.setLayout(og)
        root.addWidget(ocr_box)

        # 点击区
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
        note = QLabel("点击抓取后会立即出现全屏十字光标，直接点击目标位置即可。右键取消。")
        note.setStyleSheet("color:#64748b;font-size:12px;")
        ag.addWidget(note, 2, 0, 1, 2)
        action_box.setLayout(ag)
        root.addWidget(action_box)

        # 实时状态
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

        # 底部控制
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

        tip = QLabel("逻辑：水位 > 高阈值执行高水位点；水位 < 低阈值执行低水位点；中间区域不操作。")
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

    def preview_ocr(self):
        if self.monitor and self.monitor.isRunning():
            return
        try:
            class R:
                def x(s): return self.cfg["ocr_left"]
                def y(s): return self.cfg["ocr_top"]
                def width(s): return self.cfg["ocr_width"]
                def height(s): return self.cfg["ocr_height"]
            value = self.ocr.recognize(screenshot_region(R()))
            if value is not None:
                self.value_label.setText(f"当前水位：{value:g}")
        except Exception:
            pass

    def read_config(self):
        self.cfg["high_threshold"] = self.high.value()
        self.cfg["low_threshold"] = self.low.value()
        self.cfg["interval"] = self.interval.value()
        self.cfg["max_valid_value"] = self.max_valid.value()
        self.cfg["clicks_per_action"] = self.clicks.value()
        self.cfg["click_enabled"] = self.enable.isChecked()
        self.cfg["window_width"] = self.width()
        self.cfg["window_height"] = self.height()

    def save(self):
        self.read_config()
        save_settings(self.cfg)
        self.log.append(f"✓ 配置已保存（窗口 {self.width()}×{self.height()}）")

    def start_monitor(self):
        if self.monitor and self.monitor.isRunning():
            return
        self.read_config()
        if self.cfg["low_threshold"] >= self.cfg["high_threshold"]:
            QMessageBox.warning(self, "参数错误", "低水位阈值必须小于高水位阈值。")
            return
        if self.cfg["max_valid_value"] <= self.cfg["high_threshold"]:
            QMessageBox.warning(self, "参数错误", "识别安全上限必须大于高水位阈值，否则高水位操作永远不会执行。")
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
            self.monitor.wait(1500)
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
        self.interval.setValue(self.cfg["interval"])
        self.max_valid.setValue(self.cfg["max_valid_value"])
        self.clicks.setValue(self.cfg["clicks_per_action"])
        self.enable.setChecked(True)
        self.ocr_info.setText(self.region_text())
        self.high_point.setText(self.point_text("high"))
        self.low_point.setText(self.point_text("low"))
        self.log.append("↺ 已恢复默认参数（未自动保存）")

    def closeEvent(self, e):
        self.read_config()
        save_settings(self.cfg)
        self.stop_monitor()
        e.accept()
