import ctypes
import struct
from io import BytesIO

PB_LITTLEENDIAN = 1
PB_BIGENDIAN = 2

class ProtoBuffer(BytesIO):
    def __init__(self, data=None, byteorder=PB_LITTLEENDIAN):
        super(ProtoBuffer, self).__init__(data)
        self.byteorder = byteorder

    def pack(self, format, *args):
        data = struct.pack(format, *args)
        self.write(data)

    def unpack(self, format):
        length = struct.calcsize(format)
        buf = self.read(length)
        return struct.unpack(format, buf)

    def read_bytes(self, length):
        return self.read(length)

    def write_bytes(self, data):
        self.pack(f"!{len(data)}s", data)

    def write_zeros(self, length):
        self.pack(f"!{length}s", b'\x00' * length)

    def _translate_byteorder_sign(self, byteorder):
        bo = byteorder or self.byteorder
        bosign = ">" if bo == PB_BIGENDIAN else "<"
        return bosign

    def read_int8(self, byteorder=None):
        bo = self._translate_byteorder_sign(byteorder)
        return self.unpack(f"{bo}b")[0]

    def write_int8(self, value, byteorder=None):
        bo = self._translate_byteorder_sign(byteorder)
        self.pack(f"{bo}b", value)

    def read_uint8(self, byteorder=None):
        bo = self._translate_byteorder_sign(byteorder)
        return self.unpack(f"{bo}B")[0]

    def write_uint8(self, value, byteorder=None):
        bo = self._translate_byteorder_sign(byteorder)
        self.pack(f"{bo}B", value)

    def read_int16(self, byteorder=None):
        bo = self._translate_byteorder_sign(byteorder)
        return self.unpack(f"{bo}h")[0]

    def write_int16(self, value, byteorder=None):
        bo = self._translate_byteorder_sign(byteorder)
        self.pack(f"{bo}h", value)

    def read_uint16(self, byteorder=None):
        bo = self._translate_byteorder_sign(byteorder)
        return self.unpack(f"{bo}H")[0]

    def write_uint16(self, value, byteorder=None):
        bo = self._translate_byteorder_sign(byteorder)
        self.pack(f"{bo}H", value)

    def read_int32(self, byteorder=None):
        bo = self._translate_byteorder_sign(byteorder)
        return self.unpack(f"{bo}i")[0]

    def write_int32(self, value, byteorder=None):
        bo = self._translate_byteorder_sign(byteorder)
        self.pack(f"{bo}i", value)

    def read_uint32(self, byteorder=None):
        bo = self._translate_byteorder_sign(byteorder)
        return self.unpack(f"{bo}I")[0]

    def write_uint32(self, value, byteorder=None):
        bo = self._translate_byteorder_sign(byteorder)
        self.pack(f"{bo}I", value)

    def read_int64(self, byteorder=None):
        bo = self._translate_byteorder_sign(byteorder)
        return self.unpack(f"{bo}q")[0]

    def write_int64(self, value, byteorder=None):
        bo = self._translate_byteorder_sign(byteorder)
        self.pack(f"{bo}q", value)

    def read_uint64(self, byteorder=None):
        bo = self._translate_byteorder_sign(byteorder)
        return self.unpack(f"{bo}Q")[0]

    def write_uint64(self, value, byteorder=None):
        bo = self._translate_byteorder_sign(byteorder)
        self.pack(f"{bo}Q", value)

    def read_fix_string(self, length, encoding='utf8'):
        buf = self.unpack(f"!{length}s")[0]
        return ctypes.string_at(buf, length).decode(encoding)

    def write_fix_string(self, value, length, encoding='utf8'):
        """padding with zeros"""
        self.pack(f"!{length}s", value.encode(encoding))
