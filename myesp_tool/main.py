import logging
import sys

from PyQt5.QtWidgets import QApplication

from myesp_tool.ui.mainwindow import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setOrganizationName("WETA")
    app.setApplicationName("MyESPTool")
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    main()