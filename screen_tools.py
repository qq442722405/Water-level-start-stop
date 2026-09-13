import mss
import numpy as np
import pyautogui
from PyQt5.QtCore import Qt, QRect, QPoint, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QPen, QCursor
from PyQt5.QtWidgets import QWidget, QApplication


def screenshot_region(rect):
    with mss.mss() as sct:
        monitor = {
            "left": int(rect.x()),
            "top": int(rect.y()),
            "width": max(1, int(rect.width())),
            "height": max(1, int(rect.height())),
        }
        img = np.array(sct.grab(monitor))
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
        self.setGeometry(QApplication.primaryScreen().virtualGeometry())
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
                # 转为屏幕绝对坐标
                r.translate(self.geometry().topLeft())
                self.selected.emit(r)
            self.close()

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 95))
        if self.start and self.end:
            r = QRect(self.start, self.end).normalized()
            p.setCompositionMode(QPainter.CompositionMode_Clear)
            p.fillRect(r, Qt.transparent)
            p.setCompositionMode(QPainter.CompositionMode_SourceOver)
            p.setPen(QPen(QColor(0, 210, 255), 2))
            p.drawRect(r)

        p.setPen(QPen(Qt.white, 1))
        p.drawText(30, 45, "框选水位数字区域：按住左键拖动；右键取消")


class PointPicker(QWidget):
    """全屏十字抓取：点击目标位置即可保存，不再需要 F8。"""
    picked = pyqtSignal(int, int)
    cancelled = pyqtSignal()

    def __init__(self, title="请点击需要操作的位置"):
        super().__init__()
        self.title = title
        self.cursor_pos = QPoint(0, 0)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setGeometry(QApplication.primaryScreen().virtualGeometry())
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setCursor(Qt.CrossCursor)

    def mouseMoveEvent(self, e):
        self.cursor_pos = e.pos()
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            g = self.mapToGlobal(e.pos())
            self.picked.emit(g.x(), g.y())
            self.close()
        elif e.button() == Qt.RightButton:
            self.cancelled.emit()
            self.close()

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 55))

        # 顶部提示
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(20, 30, 42, 230))
        p.drawRoundedRect(20, 20, 430, 54, 10, 10)
        p.setPen(QPen(Qt.white, 1))
        p.drawText(38, 43, self.title)
        p.drawText(38, 62, "左键确认坐标 · 右键取消")

        x, y = self.cursor_pos.x(), self.cursor_pos.y()
        p.setPen(QPen(QColor(0, 220, 255), 2))
        p.drawLine(x - 18, y, x + 18, y)
        p.drawLine(x, y - 18, x, y + 18)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPoint(x, y), 8, 8)
        p.drawText(x + 12, y - 12, f"({x + self.geometry().x()}, {y + self.geometry().y()})")
