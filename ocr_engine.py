import re
import cv2
import numpy as np
import ddddocr

class NumberOCR:
    def __init__(self):
        self.ocr = ddddocr.DdddOcr(show_ad=False, beta=True)

    def preprocess(self, image):
        # 针对水位数字/小数点做多版本预处理
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)

        # 保留小数点：不做过强的形态学操作
        blur = cv2.GaussianBlur(gray, (3, 3), 0)
        _, th = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return th

    def recognize(self, image):
        if image is None or image.size == 0:
            return None

        candidates = []
        versions = [image, self.preprocess(image)]

        for img in versions:
            ok, enc = cv2.imencode(".png", img)
            if not ok:
                continue
            try:
                text = self.ocr.classification(enc.tobytes())
                text = str(text).strip().replace(" ", "").replace(",", ".")
                text = re.sub(r"[^0-9.\-]", "", text)
                # 防止多个小数点导致 float 崩溃
                if text.count(".") > 1:
                    parts = text.split(".")
                    text = parts[0] + "." + "".join(parts[1:])
                if re.fullmatch(r"-?\d+(?:\.\d+)?", text):
                    candidates.append(text)
            except Exception:
                pass

        if not candidates:
            return None

        # 优先选择包含小数点的结果；否则选第一项
        decimal = [x for x in candidates if "." in x]
        result = decimal[0] if decimal else candidates[0]
        try:
            return float(result)
        except Exception:
            return None
