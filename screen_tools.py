import time
import mss
import numpy as np
import pyautogui
from PyQt5.QtCore import Qt, QRect, QPoint, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QPen
from PyQt5.QtWidgets import QWidget

def screenshot_region(rect):
    with mss.mss() as sct:
        monitor = {
            "left": int(rect.x()),
            "top": int(rect.y()),
            "width": int(rect.width()),
            "height": int(rect.height()),
        }
        img = np.array(sct.grab(monitor))
        # BGRA -> BGR
        return img[:, :, :3]

def click_point(x, y):
    pyautogui.click(int(x), int(y))

class RegionSelector(QWidget):
    selected = pyqtSignal(QRect)
    cancelled = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.start = None
        self.end = None
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setWindowState(Qt.WindowFullScreen)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setCursor(Qt.CrossCursor)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.start = e.pos()
            self.end = self.start
            self.update()
        elif e.button() == Qt.RightButton:
            self.cancelled.emit()
            self.close()

    def mouseMoveEvent(self, e):
        if self.start is not None:
            self.end = e.pos()
            self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.start is not None:
            self.end = e.pos()
            r = QRect(self.start, self.end).normalized()
            if r.width() >= 5 and r.height() >= 5:
                self.selected.emit(r)
            self.close()

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 80))
        if self.start and self.end:
            r = QRect(self.start, self.end).normalized()
            p.setCompositionMode(QPainter.CompositionMode_Clear)
            p.fillRect(r, Qt.transparent)
            p.setCompositionMode(QPainter.CompositionMode_SourceOver)
            p.setPen(QPen(QColor(0, 220, 255), 3))
            p.drawRect(r)
