import re
import cv2
import numpy as np
import ddddocr


class NumberOCR:
    """针对水位数字的 OCR，引入可调预处理参数。"""

    def __init__(self, config=None):
        self.ocr = ddddocr.DdddOcr(show_ad=False, beta=True)
        self.config = config or {}

    def update_config(self, config):
        self.config = config.copy() if config else {}

    @staticmethod
    def _odd(value, minimum=1, maximum=15):
        value = int(value)
        value = max(minimum, min(maximum, value))
        if value % 2 == 0:
            value += 1
        return min(value, maximum if maximum % 2 else maximum - 1)

    def preprocess(self, image, config=None):
        cfg = config or self.config
        if image is None or image.size == 0:
            return image

        scale = max(1, min(6, int(cfg.get("ocr_scale", 3))))
        mode = cfg.get("ocr_mode", "原图+二值化")
        threshold = max(0, min(255, int(cfg.get("ocr_threshold", 160))))
        blur_k = self._odd(cfg.get("ocr_blur", 3), 1, 15)
        contrast = float(cfg.get("ocr_contrast", 1.0))
        brightness = int(cfg.get("ocr_brightness", 0))
        sharpen = max(0, min(3, int(cfg.get("ocr_sharpen", 0))))
        invert = bool(cfg.get("ocr_invert", False))

        if image.ndim == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        if scale != 1:
            gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

        if contrast != 1.0 or brightness != 0:
            gray = cv2.convertScaleAbs(gray, alpha=contrast, beta=brightness)

        if blur_k > 1:
            gray = cv2.GaussianBlur(gray, (blur_k, blur_k), 0)

        if mode == "原图":
            out = gray
        elif mode == "灰度":
            out = gray
        elif mode == "固定阈值":
            _, out = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
        elif mode == "自适应":
            block = 11
            if block <= blur_k:
                block = blur_k + 2
                if block % 2 == 0:
                    block += 1
            out = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                         cv2.THRESH_BINARY, block, 2)
        else:  # 原图+二值化
            # 默认采用 OTSU，对不同亮度的网页数字通常更稳。
            _, out = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        if sharpen > 0:
            for _ in range(sharpen):
                kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
                out = cv2.filter2D(out, -1, kernel)

        if invert:
            out = cv2.bitwise_not(out)
        return out

    @staticmethod
    def normalize_text(text):
        text = str(text).strip().replace(" ", "").replace(",", ".")
        text = re.sub(r"[^0-9.\-]", "", text)
        # 常见 OCR 小数点重复错误：只保留第一个小数点
        if text.count(".") > 1:
            parts = text.split(".")
            text = parts[0] + "." + "".join(parts[1:])
        if not re.fullmatch(r"-?\d+(?:\.\d+)?", text):
            return None
        try:
            return float(text)
        except Exception:
            return None

    def recognize(self, image, config=None, return_detail=False):
        if image is None or image.size == 0:
            return (None, []) if return_detail else None

        cfg = config or self.config
        candidates = []
        detail = []

        # 原图 + 调整后的图各识别一次，避免单一预处理失败。
        versions = [("原图", image), ("调整后", self.preprocess(image, cfg))]
        for name, img in versions:
            ok, enc = cv2.imencode(".png", img)
            if not ok:
                continue
            try:
                raw = self.ocr.classification(enc.tobytes())
                value = self.normalize_text(raw)
                detail.append({"name": name, "raw": str(raw), "value": value})
                if value is not None:
                    candidates.append((value, str(raw), name))
            except Exception as e:
                detail.append({"name": name, "raw": f"错误：{e}", "value": None})

        if not candidates:
            return (None, detail) if return_detail else None

        # 多版本结果优先选择带小数点且格式更接近水位值的结果；否则取第一项。
        decimal = [c for c in candidates if "." in c[1]]
        chosen = decimal[0] if decimal else candidates[0]
        value = chosen[0]
        return (value, detail) if return_detail else value
