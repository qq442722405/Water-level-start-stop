import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt
from ui import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # 开发环境从当前目录读取；PyInstaller 后从 exe 同目录读取
    icon_path = "app.ico"
    app.setWindowIcon(QIcon(icon_path))

    win = MainWindow()
    win.setWindowIcon(QIcon(icon_path))
    win.show()
    sys.exit(app.exec_())
