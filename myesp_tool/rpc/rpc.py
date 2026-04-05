import logging
import socket
from io import BytesIO
from typing import Union, List

import serial

from myesp_tool.rpc import utils
from myesp_tool.rpc.constants import RPC_MSG_MAGIC, RPC_MSG_VERSION, RPCMsgType, CONFIG_NS_MAX_SIZE, \
    CONFIG_KEY_MAX_SIZE, ConfigValType
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


def build_light_ctl_msg(addr_list: List[PeerAddress], pos_x: int, pos_y: int, pos_z: int,
                        mode: int = 0, brightness: int = 100) -> RPCMessage:
    """
    灯光控制请求
    data:
      [0]      addrs_num   1B    目标设备数 N（0=广播）
      [1]      addr_list   6*N   目标 MAC 地址列表
      [1+6N]   ctl         5B    灯光控制参数
        [+0]   pos.x       1B
        [+1]   pos.y       1B
        [+2]   pos.z       1B
        [+3]   mode        1B    灯光模式 (0=基础, 1=呼吸, 2=闪烁)
        [+4]   brightness  1B    亮度 (0~100)
    """
    pb = ProtoBuffer()
    pb.write_uint8(len(addr_list))
    for addr in addr_list:
        pb.write_bytes(addr.peer_addr)
    pb.write_uint8(pos_x)
    pb.write_uint8(pos_y)
    pb.write_uint8(pos_z)
    pb.write_uint8(mode)
    pb.write_uint8(brightness)
    return RPCMessage(mtype=RPCMsgType.CMD_DEVICE_LIGHT_CTL_REQ, payload=pb.getvalue())

def build_channel_set_msg(addr_list: List[PeerAddress], channel: int) -> RPCMessage:
    """
    频道切换请求
    data:
      [0]      channel   1B    通道
    """
    pb = ProtoBuffer()
    pb.write_uint8(len(addr_list))
    for addr in addr_list:
        pb.write_bytes(addr.peer_addr)
    pb.write_uint8(channel)
    return RPCMessage(mtype=RPCMsgType.CMD_DEVICE_SET_CHANNEL_REQ, payload=pb.getvalue())

def build_device_reboot_msg(addr_list: List[PeerAddress], delay: int) -> RPCMessage:
    """
    :param addr_list:
    :param delay: 指定延时 <delay> ms 后重启
    :return:
    """
    pb = ProtoBuffer()
    pb.write_uint8(len(addr_list))
    for addr in addr_list:
        pb.write_bytes(addr.peer_addr)
    pb.write_uint16(delay)
    return RPCMessage(mtype=RPCMsgType.CMD_DEVICE_REBOOT_REQ, payload=pb.getvalue())

def build_config_get_msg(addr_list: List[PeerAddress], key) -> RPCMessage:
    """
    获取设备配置

    :param addr_list:
    :param key: 配置项 key
    :return:
    """
    pb = ProtoBuffer()
    pb.write_uint8(len(addr_list))
    for addr in addr_list:
        pb.write_bytes(addr.peer_addr)
    pb.write_fix_string("app", CONFIG_NS_MAX_SIZE)
    pb.write_fix_string(key, CONFIG_KEY_MAX_SIZE)
    pb.write_uint8(ConfigValType.TYPE_ANY)
    return RPCMessage(mtype=RPCMsgType.CMD_DEVICE_CONFIG_GET_REQ, payload=pb.getvalue())

def build_config_set_msg(addr_list: List[PeerAddress], key, vtype, value) -> RPCMessage:
    """

    :param addr_list:
    :param key: 配置项 key
    :param vtype: 配置项值类型
    :param value: 值
    :return:
    """
    pb = ProtoBuffer()
    pb.write_uint8(len(addr_list))
    for addr in addr_list:
        pb.write_bytes(addr.peer_addr)
    pb.write_fix_string("app", CONFIG_NS_MAX_SIZE)
    pb.write_fix_string(key, CONFIG_KEY_MAX_SIZE)
    pb.write_uint8(vtype)
    if vtype == ConfigValType.TYPE_I8:
        pb.write_int8(value)
    elif vtype == ConfigValType.TYPE_U8:
        pb.write_uint8(value)
    if vtype == ConfigValType.TYPE_I16:
        pb.write_int16(value)
    elif vtype == ConfigValType.TYPE_U16:
        pb.write_uint16(value)
    if vtype == ConfigValType.TYPE_I32:
        pb.write_int32(value)
    elif vtype == ConfigValType.TYPE_U32:
        pb.write_uint32(value)
    if vtype == ConfigValType.TYPE_STR:
        data = value.encode("utf-8")
        pb.write_bytes(data, len(data))
    elif vtype == ConfigValType.TYPE_U32:
        pb.write_bytes(value, len(value))
    return RPCMessage(mtype=RPCMsgType.CMD_DEVICE_CONFIG_SET_REQ, payload=pb.getvalue())
