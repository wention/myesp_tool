import logging
import socket
from io import BytesIO
from typing import Union, List

import serial

from myesp_tool.rpc import utils
from myesp_tool.rpc.constants import RPC_MSG_MAGIC, RPC_MSG_VERSION, RPCMsgType
from myesp_tool.rpc.crc import esp_crc16_le
from myesp_tool.rpc.exceptions import RPCInvalidPktError, RPCIncompletePktError
from myesp_tool.rpc.protobuffer import ProtoBuffer, PB_LITTLEENDIAN

LOG = logging.getLogger(__name__)

class GatewayTCPRPC(object):
    def __init__(self, address):
        self.address = address
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.is_connected = False

    def connect(self):
        self.sock.connect(self.address)
        self.is_connected = True

    def send(self, data):
        if not self.is_connected:
            self.connect()
        self.sock.send(data)

    def recv(self, size):
        if not self.is_connected:
            self.connect()
        data = self.sock.recv(size)
        return data

class RPCMessage(object):
    def __init__(self, mtype=None, version=RPC_MSG_VERSION, payload=None, magic=RPC_MSG_MAGIC, crc=None):
        self._magic = magic
        self._version = version
        self._mtype = mtype
        self._payload = payload
        self._crc = None

    @property
    def mtype(self):
        return self._mtype

    @mtype.setter
    def mtype(self, value):
        self._mtype = value

    @property
    def payload_len(self) -> int:
        if self._payload is None:
            return 0

        return len(self._payload)

    @property
    def payload(self):
        return self._payload

    @payload.setter
    def payload(self, value: bytes):
        self._payload = value

    @property
    def crc(self):
        return self._crc

    def to_pkt(self):
        pb = ProtoBuffer()
        pb.write_uint16(self._magic)
        pb.write_uint16(self._version)
        pb.write_uint8(self._mtype)
        if self._payload:
            pb.write_uint16(len(self._payload))
            pb.write_bytes(self._payload)
        else:
            pb.write_uint16(0)

        crc = esp_crc16_le(0, pb.getvalue())
        pb.write_uint16(crc)
        return pb.getvalue()

    @classmethod
    def from_pkt(cls, pkt: bytes):
        pb = ProtoBuffer(pkt)

        magic = pb.read_uint16()
        version = pb.read_uint16()
        mtype = pb.read_uint8()
        payload_len = pb.read_uint16()

        pkt_len = 9 + payload_len

        # 检测报文是否有效
        if magic != RPC_MSG_MAGIC:
            raise RPCInvalidPktError(f"Invalid packet magic: 0x{magic:04X}, expected 0x{RPC_MSG_MAGIC:04X}")

        # 检测报文是否完整
        if len(pkt) != pkt_len:
            raise RPCIncompletePktError(f"Incomplete packet: expected {pkt_len} bytes, got {len(pkt)} bytes")

        payload = None
        if payload_len > 0:
            payload = pb.read_bytes(payload_len)
        crc = pb.read_uint16()

        return cls(mtype=mtype, version=version, payload=payload, magic=magic, crc=crc)

    @classmethod
    def detect_head(cls, pkt: bytes):
        """解析报文头部，返回 (magic, version, mtype, payload_len)。
        抛出 RPCIncompletePktError 如果头部不完整，RPCInvalidPktError 如果 magic 无效。"""
        header_size = 7  # magic(2) + version(2) + mtype(1) + payload_len(2)
        if len(pkt) < header_size:
            raise RPCIncompletePktError(f"Incomplete header: expected {header_size} bytes, got {len(pkt)} bytes")

        pb = ProtoBuffer(pkt)
        magic = pb.read_uint16()
        if magic != RPC_MSG_MAGIC:
            raise RPCInvalidPktError(f"Invalid packet magic: 0x{magic:04X}, expected 0x{RPC_MSG_MAGIC:04X}")

        version = pb.read_uint16()
        mtype = pb.read_uint8()
        payload_len = pb.read_uint16()

        return magic, version, mtype, payload_len


class GatewaySerialRPC(object):
    def __init__(self, port):
        self.port = port
        self.serial = serial.Serial(port, 115200, bytesize=8, parity='N', stopbits=1)
        self.is_connected = False

    def write(self, data):
        if not self.serial.is_open:
            self.serial.open()
        self.serial.write(data)

    def read(self, size):
        if not self.serial.is_open:
            self.serial.open()
        data = self.serial.read(size)
        return data

    def write_message(self, msg: RPCMessage):
        pkt = msg.to_pkt()
        LOG.debug(f"writing msg {RPCMsgType(msg.mtype).name}: {len(pkt)} bytes")
        LOG.debug("DUMP: \n%s", utils.hexdump(pkt))
        self.write(pkt)

    def read_message(self) -> RPCMessage:
        header_size = 7

        data = self.read(header_size)
        _, _, mtype, payload_len = RPCMessage.detect_head(data)

        remaining = payload_len + 2  # payload + crc(2)
        rest = self.read(remaining)
        if len(rest) < remaining:
            total = header_size + len(rest)
            expected = header_size + remaining
            raise RPCIncompletePktError(f"Incomplete packet: expected {expected} bytes, got {total} bytes")

        pkt = data + rest

        LOG.debug(f"read msg {RPCMsgType(mtype).name}: {len(pkt)} bytes")
        LOG.debug("DUMP: \n%s", utils.hexdump(pkt))
        return RPCMessage.from_pkt(pkt)

class PeerAddress:
    def __init__(self, peer_addr: Union[str, bytes]):
        if isinstance(peer_addr, str):
            self.peer_addr = utils.str_to_peer_addr(peer_addr)
        else:
            self.peer_addr = peer_addr[:6]

    def __str__(self):
        return utils.peer_addr_to_str(self.peer_addr)



def build_upgrade_req_msg(addr_list: List[PeerAddress], sha256: bytes, firmware_size: int) -> RPCMessage:
    """
    // UPGRADE 升级
    typedef struct {
        // 设备数量
        uint32_t firmware_size;
        uint8_t shasum256[16];
        uint8_t num;
        uint8_t peer_addr[6][0];
    } __attribute__((packed)) device_upgrade_req_t;

    :param addr_list:
    :param sha256:
    :param firmware_size:
    :return:
    """
    pb = ProtoBuffer()
    pb.write_uint32(firmware_size)
    pb.write_bytes(sha256)
    pb.write_uint8(len(addr_list))
    for addr in addr_list:
        pb.write_bytes(addr.peer_addr)

    return RPCMessage(mtype=RPCMsgType.CMD_DEVICE_UPGRADE_REQ, payload=pb.getvalue())