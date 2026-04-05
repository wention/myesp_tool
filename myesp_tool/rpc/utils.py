import hashlib


def hexdump(data, bytes_per_line=16):
    """
    生成类似 hexdump -C 格式的输出

    Args:
        data: 字节数据（bytes、bytearray 或支持索引的对象）
        bytes_per_line: 每行显示的字节数，默认 16
    """
    if isinstance(data, str):
        data = data.encode()

    result = []
    length = len(data)

    for offset in range(0, length, bytes_per_line):
        # 偏移量（8位十六进制）
        line = [f"{offset:08x}  "]

        # 十六进制部分
        chunk = data[offset:offset + bytes_per_line]
        hex_bytes = []
        for b in chunk:
            hex_bytes.append(f"{b:02x}")

        # 不够 bytes_per_line 时用空格填充
        while len(hex_bytes) < bytes_per_line:
            hex_bytes.append("  ")

        # 每 8 个字节加一个空格分隔
        for i in range(0, len(hex_bytes), 2):
            line.append(" ".join(hex_bytes[i:i+2]))
            if i == 6:
                line.append("")

        # 添加分隔符
        line.append("  |")

        # ASCII 部分
        ascii_part = []
        for b in chunk:
            # 可打印字符范围 32-126，其他显示为 '.'
            if 32 <= b <= 126:
                ascii_part.append(chr(b))
            else:
                ascii_part.append('.')
        line.append("".join(ascii_part))

        result.append(" ".join(line))

    return "\n".join(result)


def peer_addr_to_str(peer_addr: bytes) -> str:
    """将字节形式的 MAC 地址转换为字符串格式，如 'AA:BB:CC:DD:EE:FF'"""
    return ":".join(f"{b:02X}" for b in peer_addr)


def str_to_peer_addr(peer_addr: str) -> bytes:
    """将字符串格式的 MAC 地址转换为字节，如 'AA:BB:CC:DD:EE:FF' -> 6 bytes"""
    return bytes(int(b, 16) for b in peer_addr.split(":"))

def load_file(filename: str) -> bytes:
    """读取文件内容并返回字节数据"""
    with open(filename, "rb") as f:
        return f.read()

def sha256sum(data: bytes) -> bytes:
    """计算数据的 SHA-256 校验和，返回 32 字节摘要"""
    return hashlib.sha256(data).digest()