import serial
from serial.tools import list_ports
from PyQt5.QtWidgets import QDialog, QMessageBox
from PyQt5.QtCore import pyqtSlot as Slot

from .settingsdialog_ui import Ui_SettingsDialog
from .appsettings import get_serial_config, set_serial_config
from ..utils import log_exception

BAUD_RATES = [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600]
BYTESIZE_OPTIONS = [(str(v), v) for v in (5, 6, 7, 8)]
STOPBITS_OPTIONS = [("1", 1), ("1.5", 1.5), ("2", 2)]
PARITY_OPTIONS = [
    ("None", serial.PARITY_NONE),
    ("Even", serial.PARITY_EVEN),
    ("Odd", serial.PARITY_ODD),
    ("Mark", serial.PARITY_MARK),
    ("Space", serial.PARITY_SPACE),
]


class SettingsDialog(QDialog, Ui_SettingsDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self._init_controls()
        self._load_settings()
        self._connect_signals()
        self._refresh_ports()

    def _init_controls(self):
        for rate in BAUD_RATES:
            self.edit_baudrate.addItem(str(rate), rate)

        for label, val in BYTESIZE_OPTIONS:
            self.edit_bytesize.addItem(label, val)

        for label, val in STOPBITS_OPTIONS:
            self.edit_stopbits.addItem(label, val)

        for label, val in PARITY_OPTIONS:
            self.edit_parity.addItem(label, val)

    def _load_settings(self):
        cfg = get_serial_config()
        # port 在 _refresh_ports 之后设置
        self._pending_port = cfg["port"]

        idx = self.edit_baudrate.findData(cfg["baudrate"])
        if idx >= 0:
            self.edit_baudrate.setCurrentIndex(idx)
        else:
            self.edit_baudrate.setEditText(str(cfg["baudrate"]))

        idx = self.edit_bytesize.findData(cfg["bytesize"])
        if idx >= 0:
            self.edit_bytesize.setCurrentIndex(idx)

        idx = self.edit_stopbits.findData(cfg["stopbits"])
        if idx >= 0:
            self.edit_stopbits.setCurrentIndex(idx)

        idx = self.edit_parity.findData(cfg["parity"])
        if idx >= 0:
            self.edit_parity.setCurrentIndex(idx)

        self.edit_timeout.setValue(cfg["timeout"])

    def _connect_signals(self):
        self.btn_refresh_ports.clicked.connect(self._refresh_ports)
        self.buttonBox.accepted.connect(self._save_and_accept)

    @Slot()
    @log_exception
    def _refresh_ports(self):
        current = getattr(self, "_pending_port", None) or self.edit_port.currentText()
        self.edit_port.clear()
        for info in sorted(list_ports.comports(), key=lambda p: p.device):
            self.edit_port.addItem(f"{info.device} - {info.description}", info.device)
        idx = self.edit_port.findData(current)
        if idx >= 0:
            self.edit_port.setCurrentIndex(idx)
        elif self.edit_port.count() > 0:
            self.edit_port.setCurrentIndex(0)
        else:
            self.edit_port.setEditText(current)

    @Slot()
    @log_exception
    def _save_and_accept(self):
        port = self.edit_port.currentData() or self.edit_port.currentText()
        if not port.strip():
            QMessageBox.warning(self, "验证错误", "请选择或输入串口端口")
            return

        try:
            baudrate = int(self.edit_baudrate.currentData() or self.edit_baudrate.currentText())
        except ValueError:
            QMessageBox.warning(self, "验证错误", "波特率无效")
            return

        set_serial_config({
            "port": port,
            "baudrate": baudrate,
            "bytesize": self.edit_bytesize.currentData(),
            "parity": self.edit_parity.currentData(),
            "stopbits": self.edit_stopbits.currentData(),
            "timeout": self.edit_timeout.value(),
        })
        self.accept()
