from PyQt5.QtCore import pyqtSlot as Slot
from PyQt5.QtWidgets import QMainWindow, QFileDialog, QAbstractItemView

from .mainwindow_ui import Ui_MainWindow
from .devicemodel import DeviceTableModel
from .workers import ScanWorker, OTAWorker
from .appsettings import get_serial_config
from .settingsdialog import SettingsDialog
from ..rpc.protobuffer import ProtoBuffer
from ..rpc.rpc import GatewaySerialRPC, RPCMessage, PeerAddress, build_light_ctl_msg, build_channel_set_msg, \
    build_config_get_msg, build_config_set_msg, build_device_reboot_msg
from ..rpc.constants import RPCMsgType, TARGET_BROADCAST, TARGET_BY_SELECT, TARGET_GROUP, TARGET_USB, \
    TARGET_LIGHT_GROUP, TARGET_GW_GROUP, CONFIG_NS_MAX_SIZE, CONFIG_KEY_MAX_SIZE, ConfigValType

LightModeOptions = [
    ("模式1", 1),
    ("模式2", 2),
    ("模式3", 3),
]

ChannelOptions = [
    ("通道1", 1),
    ("通道2", 2),
    ("通道3", 3),
    ("通道4", 4),
    ("通道5", 5),
    ("通道6", 6),
    ("通道7", 7),
    ("通道8", 8),
    ("通道9", 9),
    ("通道10", 10),
    ("通道11", 11),
    ("通道12", 12),
    ("通道13", 13),
]

TargetOptions = [
    ("广播", TARGET_BROADCAST),
    ("所选设备", TARGET_BY_SELECT),
    # ("组播", TARGET_GROUP),
    ("组播 - 灯具", TARGET_LIGHT_GROUP),
    ("组播 - 网关", TARGET_GW_GROUP),
    ("USB调试器", TARGET_USB),
]

DeviceTypeOptions = [
    ("全部", 0),
    ("灯具", 1),
    ("网关", 2),
]

RadarLinkModeOptions = [
    ("X轴联动", 0),
    ("Y轴联动", 1),
    ("XY轴联动", 2),
    ("信号联动", 3),
]


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        self._serial_config = get_serial_config()
        self.gateway_rpc = None

        # 菜单
        menu_file = self.menubar.addMenu("文件")
        action_settings = menu_file.addAction("设置")
        action_settings.setShortcut("Ctrl+,")
        action_settings.triggered.connect(self._on_settings)

        for k, v in ChannelOptions:
            self.edit_channel.addItem(k, v)

        for k, v in LightModeOptions:
            self.edit_light_mode.addItem(k, v)

        for k,v in DeviceTypeOptions:
            self.edit_device_type_filter.addItem(k, v)

        for k,v in TargetOptions:
            self.edit_target_select.addItem(k, v)

        for k,v in RadarLinkModeOptions:
            self.edit_radar_link_mode.addItem(k, v)

        # 设备列表模型
        self.device_model = DeviceTableModel(self)
        self.deviceListView.setModel(self.device_model)
        self.deviceListView.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.deviceListView.setSelectionMode(QAbstractItemView.MultiSelection)

        # 工作线程
        self._scan_worker = None
        self._ota_worker = None

        self.ota_progress.setValue(0)

    def _ensure_rpc(self):
        """懒初始化串口连接。"""
        if self.gateway_rpc is None:
            cfg = self._serial_config
            self.gateway_rpc = GatewaySerialRPC(
                port=cfg["port"],
                baudrate=cfg["baudrate"],
                bytesize=cfg["bytesize"],
                parity=cfg["parity"],
                stopbits=cfg["stopbits"],
                timeout=cfg["timeout"],
            )
        return self.gateway_rpc

    @Slot()
    def on_btn_scan_clicked(self):
        """扫描按钮 — 扫描设备。"""
        if self._scan_worker is not None and self._scan_worker.isRunning():
            return
        if self._ota_worker is not None and self._ota_worker.isRunning():
            self.statusbar.showMessage("OTA 进行中，无法扫描")
            return

        try:
            rpc = self._ensure_rpc()
        except Exception as e:
            self.statusbar.showMessage(f"串口打开失败: {e}")
            return

        self.device_model.clear()
        self.btn_scan.setEnabled(False)
        self.btn_scan.setText("扫描中...")

        self._scan_worker = ScanWorker(rpc)
        self._scan_worker.device_found.connect(self._on_device_found)
        self._scan_worker.scan_finished.connect(self._on_scan_finished)
        self._scan_worker.scan_error.connect(self._on_scan_error)
        self._scan_worker.start()

    @Slot(dict)
    def _on_device_found(self, device):
        self.device_model.add_device(device)

    @Slot()
    def _on_scan_finished(self):
        self.btn_scan.setEnabled(True)
        self.btn_scan.setText("扫描")
        self.statusbar.showMessage(f"扫描完成，发现 {self.device_model.rowCount()} 个设备")
        self._scan_worker = None

    @Slot(str)
    def _on_scan_error(self, err_msg):
        self.btn_scan.setEnabled(True)
        self.btn_scan.setText("扫描")
        self.statusbar.showMessage(f"扫描错误: {err_msg}")
        self._scan_worker = None

    @Slot()
    def on_btn_app_flash_clicked(self):
        """烧录按钮 — 开始 OTA 升级。"""
        if self._ota_worker is not None and self._ota_worker.isRunning():
            return
        if self._scan_worker is not None and self._scan_worker.isRunning():
            self.statusbar.showMessage("扫描进行中，无法烧录")
            return

        # 获取选中的设备
        rows = set(idx.row() for idx in self.deviceListView.selectionModel().selectedRows())
        if not rows:
            self.statusbar.showMessage("请先选择要升级的设备")
            return

        firmware_path = self.edit_upgrade_rom.text().strip()
        if not firmware_path:
            self.statusbar.showMessage("请先选择固件文件")
            return

        try:
            rpc = self._ensure_rpc()
        except Exception as e:
            self.statusbar.showMessage(f"串口打开失败: {e}")
            return

        peer_addrs = self.device_model.get_peer_addresses(rows)
        self.ota_progress.setValue(0)
        self.ota_status_label.setText("")
        self.btn_app_flash.setEnabled(False)
        self.btn_scan.setEnabled(False)

        self._ota_worker = OTAWorker(rpc, peer_addrs, firmware_path)
        self._ota_worker.progress_updated.connect(self.ota_progress.setValue)
        self._ota_worker.progress_detail.connect(self._on_ota_progress_detail)
        self._ota_worker.ota_finished.connect(self._on_ota_finished)
        self._ota_worker.ota_error.connect(self._on_ota_error)
        self._ota_worker.start()

    @Slot(dict)
    def _on_ota_finished(self, result):
        self.btn_app_flash.setEnabled(True)
        self.btn_scan.setEnabled(True)
        self.ota_status_label.setText("")
        n_ok = len(result["successed"])
        n_fail = len(result["unfinished"])
        self.statusbar.showMessage(f"烧录完成: 成功 {n_ok}, 失败 {n_fail}")
        self._ota_worker = None

    @Slot(str)
    def _on_ota_error(self, err_msg):
        self.btn_app_flash.setEnabled(True)
        self.btn_scan.setEnabled(True)
        self.ota_status_label.setText("")
        self.statusbar.showMessage(f"烧录错误: {err_msg}")
        self._ota_worker = None

    @Slot(int, str, str)
    def _on_ota_progress_detail(self, pct, speed_text, eta_text):
        parts = []
        if speed_text:
            parts.append(speed_text)
        if eta_text:
            parts.append(eta_text)
        self.ota_status_label.setText("  |  ".join(parts))

    @Slot()
    def on_btn_light_high_clicked(self):
        """灯亮"""
        try:
            self._ensure_rpc()
        except Exception as e:
            self.statusbar.showMessage(f"串口打开失败: {e}")
            return

        addrs = self._get_target_addrs()
        pos_x = int(self.edit_pos_x.text() or "0")
        pos_y = int(self.edit_pos_y.text() or "0")
        pos_z = int(self.edit_pos_z.text() or "0")
        msg = build_light_ctl_msg(addrs, pos_x, pos_y, pos_z, mode=0, brightness=100)
        self.gateway_rpc.write_message(msg)
        self.gateway_rpc.read_message()

    @Slot()
    def on_btn_light_low_clicked(self):
        """灯暗"""
        try:
            self._ensure_rpc()
        except Exception as e:
            self.statusbar.showMessage(f"串口打开失败: {e}")
            return

        addrs = self._get_target_addrs()
        pos_x = int(self.edit_pos_x.text() or "0")
        pos_y = int(self.edit_pos_y.text() or "0")
        pos_z = int(self.edit_pos_z.text() or "0")
        msg = build_light_ctl_msg(addrs, pos_x, pos_y, pos_z, mode=0, brightness=0)
        self.gateway_rpc.write_message(msg)
        self.gateway_rpc.read_message()

    @Slot()
    def on_btn_light_brightness_set_clicked(self):
        try:
            self._ensure_rpc()
        except Exception as e:
            self.statusbar.showMessage(f"串口打开失败: {e}")
            return

        addrs = self._get_target_addrs()
        pos_x = int(self.edit_pos_x.text() or "0")
        pos_y = int(self.edit_pos_y.text() or "0")
        pos_z = int(self.edit_pos_z.text() or "0")
        brightness = self.edit_light_brightness.value()
        msg = build_light_ctl_msg(addrs, pos_x, pos_y, pos_z, mode=0, brightness=brightness)
        self.gateway_rpc.write_message(msg)
        self.gateway_rpc.read_message()
        pass

    @Slot()
    def on_btn_light_mode_set_clicked(self):
        try:
            self._ensure_rpc()
        except Exception as e:
            self.statusbar.showMessage(f"串口打开失败: {e}")
            return

        addrs = self._get_target_addrs()
        pos_x = int(self.edit_pos_x.text() or "0")
        pos_y = int(self.edit_pos_y.text() or "0")
        pos_z = int(self.edit_pos_z.text() or "0")
        mode = self.edit_light_mode.currentData()
        msg = build_light_ctl_msg(addrs, pos_x, pos_y, pos_z, mode=mode, brightness=100)
        self.gateway_rpc.write_message(msg)
        self.gateway_rpc.read_message()

    @Slot()
    def on_btn_channel_set_clicked(self):
        try:
            self._ensure_rpc()
        except Exception as e:
            self.statusbar.showMessage(f"串口打开失败: {e}")
            return

        addrs = self._get_target_addrs()
        channel = self.edit_channel.currentData()
        msg = build_channel_set_msg(addrs, channel)
        self.gateway_rpc.write_message(msg)
        self.gateway_rpc.read_message()

    @Slot()
    def on_btn_config_read_clicked(self):
        try:
            self._ensure_rpc()
        except Exception as e:
            self.statusbar.showMessage(f"串口打开失败: {e}")
            return

        def parse_kv(msg: RPCMessage, defaultValue=None):
            if msg.mtype == RPCMsgType.CMD_ERROR:
                return defaultValue

            pb = ProtoBuffer(msg.payload)
            ns = pb.read_fix_string(CONFIG_NS_MAX_SIZE, "utf-8")
            key = pb.read_fix_string(CONFIG_KEY_MAX_SIZE, "utf-8")
            vtype = pb.read_uint8()
            value = defaultValue

            data_len = len(msg.payload) - CONFIG_NS_MAX_SIZE - CONFIG_KEY_MAX_SIZE - 1
            if vtype == ConfigValType.TYPE_I8:
                value = pb.read_int8()
            elif vtype == ConfigValType.TYPE_U8:
                value = pb.read_uint8()
            elif vtype == ConfigValType.TYPE_I16:
                value = pb.read_int16()
            elif vtype == ConfigValType.TYPE_U16:
                value = pb.read_uint16()
            elif vtype == ConfigValType.TYPE_I32:
                value = pb.read_int32()
            elif vtype == ConfigValType.TYPE_U32:
                value = pb.read_uint32()
            elif vtype == ConfigValType.TYPE_BLOB:
                value = pb.read_bytes(data_len)
            elif vtype == ConfigValType.TYPE_BLOB:
                value = pb.read_fix_string(data_len, "utf-8")

            return ns, key, vtype, value

        addrs = self._get_selected_addrs()
        if len(addrs) != 1:
            self.statusbar.showMessage(f"配置读写只能选择一个设备")
            return

        self.statusbar.showMessage(f"读取配置信息......")
        self.statusbar.repaint()

        msg = build_config_get_msg(addrs, "pos_x")
        self.gateway_rpc.write_message(msg)
        msg = self.gateway_rpc.read_message()
        _, _, _, val = parse_kv(msg)
        self.edit_pos_x.setText(str(val))

        msg = build_config_get_msg(addrs, "pos_y")
        self.gateway_rpc.write_message(msg)
        msg = self.gateway_rpc.read_message()
        _, _, _, val = parse_kv(msg, "")
        self.edit_pos_y.setText(str(val))

        msg = build_config_get_msg(addrs, "pos_z")
        self.gateway_rpc.write_message(msg)
        msg = self.gateway_rpc.read_message()
        _, _, _, val = parse_kv(msg, "")
        self.edit_pos_z.setText(str(val))

        msg = build_config_get_msg(addrs, "led_on_duty")
        self.gateway_rpc.write_message(msg)
        msg = self.gateway_rpc.read_message()
        _, _, _, val = parse_kv(msg, 100)
        self.edit_light_brightness_high.setValue(val)

        msg = build_config_get_msg(addrs, "led_off_duty")
        self.gateway_rpc.write_message(msg)
        msg = self.gateway_rpc.read_message()
        _, _, _, val = parse_kv(msg, 10)
        self.edit_light_brightness_low.setValue(val)

        msg = build_config_get_msg(addrs, "led_off_delay")
        self.gateway_rpc.write_message(msg)
        msg = self.gateway_rpc.read_message()
        _, _, _, val = parse_kv(msg, 0)
        self.edit_light_brightness_low.setValue(val)


        msg = build_config_get_msg(addrs, "radar_lk_mode")
        self.gateway_rpc.write_message(msg)
        msg = self.gateway_rpc.read_message()
        _, _, _, val = parse_kv(msg, 3)
        idx = self.edit_radar_link_mode.findData(val)
        if idx != -1:
            self.edit_radar_link_mode.setCurrentIndex(idx)

        msg = build_config_get_msg(addrs, "radar_lk_range")
        self.gateway_rpc.write_message(msg)
        msg = self.gateway_rpc.read_message()
        _, _, _, val = parse_kv(msg, -65)
        self.edit_radar_link_range.setValue(val)


        self.statusbar.showMessage(f"读取配置完成")
        pass

    @Slot()
    def on_btn_config_write_clicked(self):
        try:
            self._ensure_rpc()
        except Exception as e:
            self.statusbar.showMessage(f"串口打开失败: {e}")
            return

        addrs = self._get_selected_addrs()
        if len(addrs) != 1:
            self.statusbar.showMessage(f"配置读写只能选择一个设备")
            return

        pos_x = int(self.edit_pos_x.text())
        pos_y = int(self.edit_pos_y.text())
        pos_z = int(self.edit_pos_z.text())
        light_brightness_high = self.edit_light_brightness_high.value()
        light_brightness_low = self.edit_light_brightness_low.value()
        off_delay = self.edit_off_delay.value()
        radar_link_mode = self.edit_radar_link_mode.currentData()
        radar_link_range = self.edit_radar_link_range.value()

        self.updateStatusMessage("写入配置 pos_x")
        msg = build_config_set_msg(addrs, "pos_x", ConfigValType.TYPE_U8, pos_x)
        self.gateway_rpc.write_message(msg)
        msg = self.gateway_rpc.read_message()

        self.updateStatusMessage("写入配置 pos_y")
        msg = build_config_set_msg(addrs, "pos_y", ConfigValType.TYPE_U8, pos_y)
        self.gateway_rpc.write_message(msg)
        msg = self.gateway_rpc.read_message()

        self.updateStatusMessage("写入配置 pos_z")
        msg = build_config_set_msg(addrs, "pos_z", ConfigValType.TYPE_U8, pos_z)
        self.gateway_rpc.write_message(msg)
        msg = self.gateway_rpc.read_message()

        self.updateStatusMessage("写入配置 led_on_duty")
        msg = build_config_set_msg(addrs, "led_on_duty", ConfigValType.TYPE_U8, light_brightness_high)
        self.gateway_rpc.write_message(msg)
        msg = self.gateway_rpc.read_message()

        self.updateStatusMessage("写入配置 led_off_duty")
        msg = build_config_set_msg(addrs, "led_off_duty", ConfigValType.TYPE_U8, light_brightness_low)
        self.gateway_rpc.write_message(msg)
        msg = self.gateway_rpc.read_message()


        self.updateStatusMessage("写入配置 led_off_delay")
        msg = build_config_set_msg(addrs, "led_off_delay", ConfigValType.TYPE_U16, off_delay)
        self.gateway_rpc.write_message(msg)
        msg = self.gateway_rpc.read_message()

        self.updateStatusMessage("写入配置 radar_lk_mode")
        msg = build_config_set_msg(addrs, "radar_lk_mode", ConfigValType.TYPE_U8, radar_link_mode)
        self.gateway_rpc.write_message(msg)
        msg = self.gateway_rpc.read_message()

        self.updateStatusMessage("写入配置 radar_lk_range")
        msg = build_config_set_msg(addrs, "radar_lk_range", ConfigValType.TYPE_I8, radar_link_range)
        self.gateway_rpc.write_message(msg)
        msg = self.gateway_rpc.read_message()

    def updateStatusMessage(self, msg, repaint=False):
        self.statusbar.showMessage(msg)
        self.statusbar.repaint()

    @Slot()
    def on_btn_reboot_clicked(self):
        try:
            self._ensure_rpc()
        except Exception as e:
            self.statusbar.showMessage(f"串口打开失败: {e}")
            return

        addrs = self._get_target_addrs()
        msg = build_device_reboot_msg(addrs, 100)
        self.gateway_rpc.write_message(msg)
        self.gateway_rpc.read_message()
        pass

    def _get_target_addrs(self):
        """根据"""
        target_select = self.edit_target_select.currentData()
        if target_select == TARGET_BROADCAST:
            return [PeerAddress("ff:ff:ff:ff:ff:ff")]
        elif target_select == TARGET_LIGHT_GROUP:
            return [PeerAddress(b"ESP\x00\xff\xff")]
        elif target_select == TARGET_GW_GROUP:
            return [PeerAddress(b"ESP\x01\xff\xff")]
        elif target_select == TARGET_USB:
            return [PeerAddress("00:00:00:00:00:00")]
        elif target_select == TARGET_BY_SELECT:
            rows = set(idx.row() for idx in self.deviceListView.selectionModel().selectedRows())
            if rows:
                return self.device_model.get_peer_addresses(rows)
        return []

    def _get_selected_addrs(self):
        """获取选中设备的 PeerAddress 列表，未选中则为空列表（广播）。"""
        rows = set(idx.row() for idx in self.deviceListView.selectionModel().selectedRows())
        if rows:
            return self.device_model.get_peer_addresses(rows)
        return []

    @Slot()
    def on_btn_select_file_clicked(self):
        filename, _ = QFileDialog.getOpenFileName(self, "选择固件文件")
        if filename:
            self.edit_upgrade_rom.setText(filename)

    @Slot()
    def _on_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec_() == SettingsDialog.Accepted:
            if self.gateway_rpc is not None:
                if self.gateway_rpc.serial.is_open:
                    self.gateway_rpc.serial.close()
                self.gateway_rpc = None
            self._serial_config = get_serial_config()
            self.statusbar.showMessage(f"设置已更新，串口: {self._serial_config['port']}")
