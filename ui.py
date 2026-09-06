from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QLabel, QPushButton, QLineEdit, QDoubleSpinBox,
    QSpinBox, QGridLayout, QVBoxLayout, QHBoxLayout, QGroupBox, QTextEdit,
    QMessageBox, QCheckBox
)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QPixmap
from screen_tools import RegionSelector, screenshot_region
from settings import load_settings, save_settings
from ocr_engine import NumberOCR
from monitor import MonitorThread

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = load_settings()
        self.ocr = NumberOCR()
        self.monitor = None
        self.selector = None
        self.current_value = None
        self.setWindowTitle("水位数字自动控制")
        self.resize(980, 760)
        self.build_ui()

        self.preview_timer = QTimer(self)
        self.preview_timer.timeout.connect(self.preview_ocr)
        self.preview_timer.start(500)

    def make_double(self, value, lo=-999999, hi=999999, decimals=3, step=0.1):
        w = QDoubleSpinBox()
        w.setRange(lo, hi)
        w.setDecimals(decimals)
        w.setSingleStep(step)
        w.setValue(float(value))
        return w

    def make_int(self, value, lo=0, hi=999999):
        w = QSpinBox()
        w.setRange(lo, hi)
        w.setValue(int(value))
        return w

    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        title = QLabel("水位数字自动控制")
        title.setStyleSheet("font-size:26px;font-weight:bold;")
        root.addWidget(title)

        desc = QLabel("识别屏幕上的水位数字；高于上限点击“加水/停止”点，低于下限点击另一个控制点。")
        desc.setStyleSheet("color:#666;")
        root.addWidget(desc)

        g = QGridLayout()

        self.high = self.make_double(self.cfg["high_threshold"], -9999, 9999, 3, 0.1)
        self.low = self.make_double(self.cfg["low_threshold"], -9999, 9999, 3, 0.1)
        self.interval = self.make_double(self.cfg["interval"], 0.05, 3600, 2, 0.1)
        self.cooldown = self.make_double(self.cfg["cooldown"], 0, 3600, 2, 0.1)
        self.clicks = self.make_int(self.cfg["clicks_per_action"], 1, 20)

        g.addWidget(QLabel("高水位阈值（>）："), 0, 0)
        g.addWidget(self.high, 0, 1)
        g.addWidget(QLabel("低水位阈值（<）："), 0, 2)
        g.addWidget(self.low, 0, 3)
        g.addWidget(QLabel("检测间隔（秒）："), 1, 0)
        g.addWidget(self.interval, 1, 1)
        g.addWidget(QLabel("最小点击间隔（秒）："), 1, 2)
        g.addWidget(self.cooldown, 1, 3)
        g.addWidget(QLabel("每次动作点击次数："), 2, 0)
        g.addWidget(self.clicks, 2, 1)
        root.addLayout(g)

        ocr_box = QGroupBox("① 水位数字识别区域")
        og = QGridLayout()
        self.ocr_info = QLabel(self.region_text())
        btn_region = QPushButton("框选识别区域")
        btn_region.clicked.connect(self.select_region)
        og.addWidget(self.ocr_info, 0, 0)
        og.addWidget(btn_region, 0, 1)
        ocr_box.setLayout(og)
        root.addWidget(ocr_box)

        action_box = QGroupBox("② 自动点击坐标")
        ag = QGridLayout()
        self.high_point = QLabel(self.point_text("high"))
        self.low_point = QLabel(self.point_text("low"))
        bh = QPushButton("抓取高水位点击点")
        bl = QPushButton("抓取低水位点击点")
        bh.clicked.connect(lambda: self.capture_point("high"))
        bl.clicked.connect(lambda: self.capture_point("low"))
        ag.addWidget(self.high_point, 0, 0)
        ag.addWidget(bh, 0, 1)
        ag.addWidget(self.low_point, 1, 0)
        ag.addWidget(bl, 1, 1)
        action_box.setLayout(ag)
        root.addWidget(action_box)

        status_box = QGroupBox("③ 实时识别")
        sv = QVBoxLayout()
        self.value_label = QLabel("当前水位：--")
        self.value_label.setStyleSheet("font-size:30px;font-weight:bold;")
        self.status_label = QLabel("状态：未启动")
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(150)
        sv.addWidget(self.value_label)
        sv.addWidget(self.status_label)
        sv.addWidget(self.log)
        status_box.setLayout(sv)
        root.addWidget(status_box)

        bottom = QHBoxLayout()
        self.enable = QCheckBox("允许自动点击")
        self.enable.setChecked(bool(self.cfg.get("click_enabled", True)))
        bottom.addWidget(self.enable)

        save = QPushButton("保存配置")
        save.clicked.connect(self.save)
        start = QPushButton("开始监控")
        start.clicked.connect(self.start_monitor)
        stop = QPushButton("停止监控")
        stop.clicked.connect(self.stop_monitor)
        reset = QPushButton("恢复默认")
        reset.clicked.connect(self.reset)

        bottom.addWidget(save)
        bottom.addWidget(start)
        bottom.addWidget(stop)
        bottom.addWidget(reset)
        root.addLayout(bottom)

        tip = QLabel(
            "建议：例如高水位 2.5、低水位 2.0、检测间隔 1 秒。"
            "水位 > 2.5 时每隔设定时间点击一次；水位 < 2.0 时点击另一个点。"
        )
        tip.setWordWrap(True)
        tip.setStyleSheet("color:#777;")
        root.addWidget(tip)

    def region_text(self):
        return f"区域：X={self.cfg['ocr_left']} Y={self.cfg['ocr_top']}  W={self.cfg['ocr_width']} H={self.cfg['ocr_height']}"

    def point_text(self, kind):
        if kind == "high":
            return f"高水位点击点：X={self.cfg['high_x']} Y={self.cfg['high_y']}"
        return f"低水位点击点：X={self.cfg['low_x']} Y={self.cfg['low_y']}"

    def select_region(self):
        self.selector = RegionSelector()
        self.selector.selected.connect(self.region_selected)
        self.selector.cancelled.connect(lambda: None)
        self.selector.show()

    def region_selected(self, r):
        self.cfg["ocr_left"] = r.x()
        self.cfg["ocr_top"] = r.y()
        self.cfg["ocr_width"] = r.width()
        self.cfg["ocr_height"] = r.height()
        self.ocr_info.setText(self.region_text())
        self.log.append("已设置水位数字识别区域")

    def capture_point(self, kind):
        QMessageBox.information(self, "抓取坐标", "点击“确定”后，移动鼠标到目标按钮/位置，按 F8 抓取坐标。")
        self.pending_point = kind
        self.grab_timer = QTimer(self)
        self.grab_timer.timeout.connect(self.check_f8)
        self.grab_timer.start(50)

    def check_f8(self):
        import pyautogui
        if pyautogui.press is None:
            return
        # 使用键盘监听更可靠；这里用 pynput 动态监听
        if not hasattr(self, "_listener"):
            from pynput import keyboard
            def on_press(key):
                if key == keyboard.Key.f8:
                    x, y = pyautogui.position()
                    self.captured_xy = (x, y)
                    return False
            self._listener = keyboard.Listener(on_press=on_press)
            self._listener.start()

        if hasattr(self, "captured_xy"):
            x, y = self.captured_xy
            kind = self.pending_point
            self.cfg[f"{kind}_x"] = x
            self.cfg[f"{kind}_y"] = y
            if kind == "high":
                self.high_point.setText(self.point_text("high"))
            else:
                self.low_point.setText(self.point_text("low"))
            self.log.append(f"已抓取{('高水位' if kind == 'high' else '低水位')}点击点：X={x} Y={y}")
            del self.captured_xy
            try:
                self._listener.stop()
            except Exception:
                pass
            del self._listener
            self.grab_timer.stop()

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
        self.cfg["cooldown"] = self.cooldown.value()
        self.cfg["clicks_per_action"] = self.clicks.value()
        self.cfg["click_enabled"] = self.enable.isChecked()

    def save(self):
        self.read_config()
        save_settings(self.cfg)
        self.log.append("配置已保存")

    def start_monitor(self):
        if self.monitor and self.monitor.isRunning():
            return
        self.read_config()
        if self.cfg["low_threshold"] >= self.cfg["high_threshold"]:
            QMessageBox.warning(self, "参数错误", "低水位阈值必须小于高水位阈值。")
            return
        save_settings(self.cfg)
        self.monitor = MonitorThread(self.ocr, self.cfg)
        self.monitor.value_signal.connect(self.on_value)
        self.monitor.status_signal.connect(self.status_label.setText)
        self.monitor.action_signal.connect(lambda s: self.log.append(s))
        self.monitor.start()
        self.log.append("监控已启动")

    def stop_monitor(self):
        if self.monitor:
            self.monitor.stop()
            self.monitor.wait(1500)
            self.monitor = None
        self.status_label.setText("状态：已停止")
        self.log.append("监控已停止")

    def on_value(self, value):
        if value is None:
            return
        self.current_value = value
        self.value_label.setText(f"当前水位：{value:g}")

    def reset(self):
        from settings import DEFAULTS
        self.cfg = DEFAULTS.copy()
        self.high.setValue(self.cfg["high_threshold"])
        self.low.setValue(self.cfg["low_threshold"])
        self.interval.setValue(self.cfg["interval"])
        self.cooldown.setValue(self.cfg["cooldown"])
        self.clicks.setValue(self.cfg["clicks_per_action"])
        self.enable.setChecked(True)
        self.ocr_info.setText(self.region_text())
        self.high_point.setText(self.point_text("high"))
        self.low_point.setText(self.point_text("low"))
        self.log.append("已恢复默认参数")

    def closeEvent(self, e):
        self.stop_monitor()
        e.accept()
