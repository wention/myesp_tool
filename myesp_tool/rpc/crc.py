def esp_crc16_le(crc: int, data: bytes) -> int:
    """
    ESP32 esp_crc16_le 兼容实现。

    多项式: CRC-16/CCITT (x16+x12+x5+1) = 0x1021
    反向多项式 (LSB-first): 0x8408

    用法与 ESP-IDF 一致:
        crc = ~esp_crc16_le(~init & 0xFFFF, buf)

    参数:
        crc:  初始 CRC 值 (第一次调用传 0)
        data: 输入数据 (bytes)

    返回:
        CRC16 值 (uint16)
    """
    CRC16_POLY = 0x8408  # bit-reversed 0x1021
    crc &= 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ CRC16_POLY
            else:
                crc >>= 1
    return crc & 0xFFFF