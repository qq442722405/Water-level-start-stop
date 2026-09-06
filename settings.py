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
    "interval": 1.0,
    "high_x": 500,
    "high_y": 500,
    "low_x": 600,
    "low_y": 500,
    "click_enabled": True,
    "clicks_per_action": 1,
    "same_condition_repeat": True,
    "cooldown": 1.0
}

def load_settings():
    os.makedirs(APP_DIR, exist_ok=True)
    data = DEFAULTS.copy()
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data.update(json.load(f))
        except Exception:
            pass
    return data

def save_settings(data):
    os.makedirs(APP_DIR, exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
