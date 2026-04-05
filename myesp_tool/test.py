import ctypes
import logging
import argparse
import enum
import socket
import struct
import time

from myesp_tool.rpc import utils
from myesp_tool.rpc.protobuffer import ProtoBuffer

LOG = logging.getLogger(__name__)

from myesp_tool.rpc.constants import RPCMsgType
from myesp_tool.rpc.rpc import GatewaySerialRPC, RPCMessage, PeerAddress, build_upgrade_req_msg
from myesp_tool.rpc.utils import hexdump

def test_probe(rpc: GatewaySerialRPC):
    rpc.write_message(RPCMessage(mtype=RPCMsgType.CMD_SCAN_REQ))

    msg = rpc.read_message()
    if msg.mtype == RPCMsgType.CMD_SCAN_REP:
        pass

def test_ota(rpc: GatewaySerialRPC):
    rom_filename = "/home/wention/Work/myesp_app/build/myesp_app.bin"

    rom_data = utils.load_file(rom_filename)
    sha256sum = utils.sha256sum(rom_data)

    peer_addrs = [
        PeerAddress("40:4c:ca:57:a4:f0"),
    ]
    rpc.write_message(build_upgrade_req_msg(peer_addrs, sha256sum[:16], len(rom_data)))

    while True:
        msg = rpc.read_message()

        if msg.mtype == RPCMsgType.CMD_DEVICE_UPGRADE_DATA_REQ:
            pb = ProtoBuffer(msg.payload)
            offset = pb.read_uint32()
            size = pb.read_uint32()

            rpc.write_message(RPCMessage(RPCMsgType.CMD_DEVICE_UPGRADE_DATA_REP, payload=rom_data[offset:offset + size]))

            LOG.info("upgrade progress: %.2f%%", offset / len(rom_data) * 100)
            pass
        elif msg.mtype == RPCMsgType.CMD_DEVICE_UPGRADE_REP:
            LOG.info("upgrade progress: 100%")
            break
        pass
    pass

def main():
    # rpc = GatewaySerialRPC("/dev/ttyUSB0")

    # test_probe(rpc)
    # test_ota(rpc)

    data = b"app\x00\x00\x00\x00\x00"
    a = ctypes.string_at(data).decode("utf-8")
    LOG.info("a=%s", a)
    pass


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    main()