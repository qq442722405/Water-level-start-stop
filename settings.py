import json
import os

APP_DIR = os.path.join(os.getenv("APPDATA") or os.path.expanduser("~"), "WaterLevelAutoControl")
SETTINGS_FILE = os.path.join(APP_DIR, "config.json")

DEFAULTS = {
    "ocr_left": 100,
    "ocr_top": 100,
    "ocr_width": 300,
    "ocr_height": 120,
    "high_threshold": 2.5,
    "low_threshold": 2.0,
    "detection_interval": 1.0,
    "operation_interval": 3.0,
    "high_x": 500,
    "high_y": 500,
    "low_x": 600,
    "low_y": 500,
    "click_enabled": True,
    "clicks_per_action": 1,
    "safety_operator": ">",
    "safety_value": 20.0,
    "window_width": 900,
    "window_height": 720,
    # OCR 调整参数
    "ocr_scale": 3,
    "ocr_mode": "原图+二值化",
    "ocr_threshold": 160,
    "ocr_blur": 3,
    "ocr_contrast": 1.0,
    "ocr_brightness": 0,
    "ocr_sharpen": 0,
    "ocr_invert": False,
}


def load_settings():
    os.makedirs(APP_DIR, exist_ok=True)
    data = DEFAULTS.copy()
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            if isinstance(saved, dict):
                data.update(saved)
                # 兼容旧版 interval / max_valid_value 配置
                if "detection_interval" not in saved and "interval" in saved:
                    data["detection_interval"] = saved["interval"]
                if "operation_interval" not in saved:
                    data["operation_interval"] = saved.get("interval", DEFAULTS["operation_interval"])
                if "safety_value" not in saved and "max_valid_value" in saved:
                    data["safety_value"] = saved["max_valid_value"]
                if "safety_operator" not in saved:
                    data["safety_operator"] = ">"
        except Exception:
            pass
    return data


def save_settings(data):
    os.makedirs(APP_DIR, exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
