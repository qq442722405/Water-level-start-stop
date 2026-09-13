import time
from PyQt5.QtCore import QThread, pyqtSignal
from screen_tools import screenshot_region, click_point


class MonitorThread(QThread):
    value_signal = pyqtSignal(object)
    status_signal = pyqtSignal(str)
    action_signal = pyqtSignal(str)

    def __init__(self, ocr, config):
        super().__init__()
        self.ocr = ocr
        self.cfg = config.copy()
        self.running = True
        self.last_action = 0.0

    def stop(self):
        self.running = False

    def run(self):
        rect = type("R", (), {
            "x": lambda s: self.cfg["ocr_left"],
            "y": lambda s: self.cfg["ocr_top"],
            "width": lambda s: self.cfg["ocr_width"],
            "height": lambda s: self.cfg["ocr_height"],
        })()

        while self.running:
            started = time.time()
            try:
                img = screenshot_region(rect)
                value = self.ocr.recognize(img)
                self.value_signal.emit(value)

                if value is None:
                    self.status_signal.emit("状态：未识别到有效数字")
                else:
                    high = float(self.cfg["high_threshold"])
                    low = float(self.cfg["low_threshold"])
                    interval = max(0.05, float(self.cfg["interval"]))
                    max_valid = float(self.cfg.get("max_valid_value", 20.0))
                    self.status_signal.emit(f"状态：识别到 {value:g}")

                    # OCR 安全上限：超过该值视为疑似识别错误，绝不执行点击
                    if value > max_valid:
                        self.action_signal.emit(
                            f"⚠ 识别值 {value:g} > 安全上限 {max_valid:g}，本次不执行点击"
                        )
                    else:
                        now = time.time()
                        if self.cfg.get("click_enabled", True) and now - self.last_action >= interval:
                            if value > high:
                                self.do_click(
                                    self.cfg["high_x"], self.cfg["high_y"],
                                    self.cfg.get("clicks_per_action", 1),
                                    f"水位 {value:g} > {high:g}，执行高水位操作"
                                )
                            elif value < low:
                                self.do_click(
                                    self.cfg["low_x"], self.cfg["low_y"],
                                    self.cfg.get("clicks_per_action", 1),
                                    f"水位 {value:g} < {low:g}，执行低水位操作"
                                )

            except Exception as e:
                self.status_signal.emit(f"状态：监控错误 - {e}")

            elapsed = time.time() - started
            wait = max(0.02, float(self.cfg["interval"]) - elapsed)
            self.msleep(int(wait * 1000))

    def do_click(self, x, y, count, message):
        for _ in range(max(1, int(count))):
            if not self.running:
                break
            click_point(x, y)
            if count > 1:
                time.sleep(0.08)
        self.last_action = time.time()
        self.action_signal.emit(message)
