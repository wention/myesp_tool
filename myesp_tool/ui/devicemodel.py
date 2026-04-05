from PyQt5.QtCore import Qt, QAbstractTableModel, QModelIndex

from ..rpc.rpc import PeerAddress


class DeviceTableModel(QAbstractTableModel):
    DEVICE_TYPES = {0: "灯具", 1: "网关"}
    COLUMNS = ["MAC 地址", "类型", "通道", "位置", "RSSI", "状态"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._devices = []

    def rowCount(self, parent=QModelIndex()):
        return len(self._devices)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or role != Qt.DisplayRole:
            return None
        device = self._devices[index.row()]
        col = index.column()
        if col == 0:
            return device["mac"]
        if col == 1:
            return self.DEVICE_TYPES.get(device.get("device_type"), str(device.get("device_type", "")))
        if col == 2:
            return str(device.get("channel", ""))
        if col == 3:
            return f"({device.get('pos_x', '')}, {device.get('pos_y', '')}, {device.get('pos_z', '')})"
        if col == 4:
            return str(device.get("rssi", ""))
        if col == 5:
            return device.get("status", "")

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.COLUMNS[section]

    def clear(self):
        self.beginResetModel()
        self._devices.clear()
        self.endResetModel()

    def add_device(self, device: dict):
        row = len(self._devices)
        self.beginInsertRows(QModelIndex(), row, row)
        self._devices.append(device)
        self.endInsertRows()

    def get_peer_addresses(self, rows):
        return [PeerAddress(self._devices[r]["mac"]) for r in rows]
