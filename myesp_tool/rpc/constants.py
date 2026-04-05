import enum
from enum import IntEnum, auto

RPC_MSG_MAGIC = 0x1ff2
RPC_MSG_VERSION = 0x0100


class RPCMsgType(enum.IntEnum):
    def _generate_next_value_(name, start, count, last_values):
        return count  # 'count' starts at 0

    # 设备扫描
    CMD_DEVICE_SCAN_REQ = auto()
    CMD_DEVICE_SCAN_REP = auto()

    # 获取设备信息
    CMD_DEVICE_INFO_REQ = auto()
    CMD_DEVICE_INFO_REP = auto()

    # 设置设备频道
    CMD_DEVICE_SET_CHANNEL_REQ = auto()
    CMD_DEVICE_SET_CHANNEL_REP = auto()

    # 灯光控制
    CMD_DEVICE_LIGHT_CTL_REQ = auto()
    CMD_DEVICE_LIGHT_CTL_REP = auto()

    # 设备配置
    CMD_DEVICE_CONFIG_GET_REQ = auto()
    CMD_DEVICE_CONFIG_GET_REP = auto()
    CMD_DEVICE_CONFIG_SET_REQ = auto()
    CMD_DEVICE_CONFIG_SET_REP = auto()

    # 设备升级
    CMD_DEVICE_UPGRADE_REQ = auto()
    CMD_DEVICE_UPGRADE_DATA_REQ = auto()
    CMD_DEVICE_UPGRADE_DATA_REP = auto()
    CMD_DEVICE_UPGRADE_REP = auto()

    # 设备状态上报
    CMD_DEVICE_REPORT_SUB = auto()
    CMD_DEVICE_REPORT_UNSUB = auto()
    CMD_DEVICE_REPORT_PUB = auto()

    # 重启
    CMD_DEVICE_REBOOT_REQ = auto()
    CMD_DEVICE_REBOOT_REP = auto()

    CMD_ERROR = auto()
    CMD_ACK = auto()


class ConfigValType(enum.IntEnum):
    TYPE_U8    = 0x01
    TYPE_I8    = 0x11
    TYPE_U16   = 0x02
    TYPE_I16   = 0x12
    TYPE_U32   = 0x04
    TYPE_I32   = 0x14
    TYPE_U64   = 0x08
    TYPE_I64   = 0x18
    TYPE_STR   = 0x21
    TYPE_BLOB  = 0x42
    TYPE_ANY   = 0xff

CONFIG_KEY_MAX_SIZE = 15
CONFIG_NS_MAX_SIZE = 15


TARGET_BROADCAST = 1
TARGET_BY_SELECT = 2
TARGET_GROUP = 3
TARGET_LIGHT_GROUP = 4
TARGET_GW_GROUP = 5
TARGET_USB = 6
