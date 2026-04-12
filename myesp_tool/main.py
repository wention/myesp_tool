import logging
import sys

from PyQt5.QtWidgets import QApplication

from myesp_tool.ui.mainwindow import MainWindow
from myesp_tool.utils import setup_file_logging


def main():
    app = QApplication(sys.argv)
    app.setOrganizationName("WETA")
    app.setApplicationName("MyESPTool")

    setup_file_logging()

    w = MainWindow()
    w.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    main()