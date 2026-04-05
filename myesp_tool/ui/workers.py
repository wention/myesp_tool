import logging

from PyQt5.QtCore import QThread, pyqtSignal as Signal

from ..rpc.constants import RPCMsgType
from ..rpc.protobuffer import ProtoBuffer
from ..rpc.rpc import GatewaySerialRPC, RPCMessage, PeerAddress, build_upgrade_req_msg
from ..rpc import utils

LOG = logging.getLogger(__name__)


class ScanWorker(QThread):
    device_found = Signal(dict)
    scan_finished = Signal()
    scan_error = Signal(str)

    def __init__(self, rpc: GatewaySerialRPC, parent=None):
        super().__init__(parent)
        self.rpc = rpc

    def run(self):
        try:
            self.rpc.write_message(RPCMessage(mtype=RPCMsgType.CMD_DEVICE_SCAN_REQ))
            msg = self.rpc.read_message()
            if msg.mtype == RPCMsgType.CMD_DEVICE_SCAN_REP and msg.payload:
                self._parse_scan_reply(msg.payload)
            self.scan_finished.emit()
        except Exception as e:
            LOG.exception(e)
            self.scan_error.emit(str(e))

    def _parse_scan_reply(self, payload: bytes):
        """解析扫描回复 payload。假设为 N 个连续的 6 字节 MAC 地址。"""
        pb = ProtoBuffer(payload)
        n = pb.read_uint8()
        for i in range(n):
            addr = PeerAddress(pb.read_bytes(6))
            pos_x = pb.read_uint8()
            pos_y = pb.read_uint8()
            pos_z = pb.read_uint8()
            device_type = pb.read_uint8()
            channel = pb.read_uint8()
            rssi = pb.read_int8()

            self.device_found.emit({
                "mac": str(addr), "pos_x": pos_x, "pos_y": pos_y, "pos_z": pos_z,
                "device_type": device_type, "channel": channel, "rssi": rssi,
            })


class OTAWorker(QThread):
    progress_updated = Signal(int)
    ota_finished = Signal(dict)
    ota_error = Signal(str)

    def __init__(self, rpc: GatewaySerialRPC, peer_addrs: list, firmware_path: str, parent=None):
        super().__init__(parent)
        self.rpc = rpc
        self.peer_addrs = peer_addrs
        self.firmware_path = firmware_path

    def run(self):
        try:
            rom_data = utils.load_file(self.firmware_path)
            sha256sum = utils.sha256sum(rom_data)
            msg = build_upgrade_req_msg(self.peer_addrs, sha256sum[:16], len(rom_data))
            self.rpc.write_message(msg)

            while True:
                msg = self.rpc.read_message()
                if msg.mtype == RPCMsgType.CMD_DEVICE_UPGRADE_DATA_REQ:
                    pb = ProtoBuffer(msg.payload)
                    offset = pb.read_uint32()
                    size = pb.read_uint32()
                    chunk = rom_data[offset:offset + size]
                    self.rpc.write_message(
                        RPCMessage(RPCMsgType.CMD_DEVICE_UPGRADE_DATA_REP, payload=chunk)
                    )
                    pct = int(offset / len(rom_data) * 100)
                    self.progress_updated.emit(pct)
                elif msg.mtype == RPCMsgType.CMD_DEVICE_UPGRADE_REP:
                    self.progress_updated.emit(100)
                    result = self._parse_upgrade_rep(msg.payload)
                    self.ota_finished.emit(result)
                    break
                elif msg.mtype == RPCMsgType.CMD_ERROR:
                    self.ota_error.emit("设备报告升级错误")
                    break
        except Exception as e:
            LOG.exception(e)
            self.ota_error.emit(str(e))

    def _parse_upgrade_rep(self, payload: bytes) -> dict:
        """解析升级回复：unfinished/successed/requested 设备 MAC 列表。"""
        pb = ProtoBuffer(payload)

        unfinished_num = pb.read_uint8()
        unfinished = [str(PeerAddress(pb.read_bytes(6))) for _ in range(unfinished_num)]

        successed_num = pb.read_uint8()
        successed = [str(PeerAddress(pb.read_bytes(6))) for _ in range(successed_num)]

        requested_num = pb.read_uint8()
        requested = [str(PeerAddress(pb.read_bytes(6))) for _ in range(requested_num)]

        return {
            "unfinished": unfinished,
            "successed": successed,
            "requested": requested,
        }
