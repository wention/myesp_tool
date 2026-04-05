from PyQt5.QtCore import pyqtSignal as Signal, pyqtSlot as Slot
from PyQt5.QtNetwork import QTcpSocket
from PyQt5.QtWidgets import QMainWindow, QFileDialog

from .mainwindow_ui import Ui_MainWindow
from ..rpc.rpc import GatewaySerialRPC



class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        self.deviceListmodel =
        self.tableView.setModel(self.model)

        self.gateway_rpc = GatewaySerialRPC("/dev/ttyUSB0")

    @Slot()
    def on_btn_light_high_clicked(self):
        self.gateway_rpc.write(bytes.fromhex("04 93 09 00 00 00 00 00  01"))
        pass

    @Slot()
    def on_btn_light_low_clicked(self):
        self.gateway_rpc.write(bytes.fromhex("04 93 09 00 00 00 00 00  00"))
        pass

    @Slot()
    def on_btn_select_file_clicked(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Open File")
        self.edit_upgrade_rom.setText(filename)