from PyQt5.QtCore import QSettings

ORGANIZATION = "WETA"
APPLICATION = "MyESPTool"

_SERIAL_DEFAULTS = {
    "port": "/dev/ttyUSB0",
    "baudrate": 115200,
    "bytesize": 8,
    "parity": "N",
    "stopbits": 1,
    "timeout": 10.0,
}


def get_settings() -> QSettings:
    return QSettings(ORGANIZATION, APPLICATION)


def get_serial_config() -> dict:
    s = get_settings()
    config = {}
    for key, default in _SERIAL_DEFAULTS.items():
        val = s.value(f"serial/{key}", default)
        if key in ("baudrate", "bytesize", "stopbits"):
            val = int(val)
        elif key == "timeout":
            val = float(val)
        config[key] = val
    return config


def set_serial_config(config: dict):
    s = get_settings()
    for key, value in config.items():
        s.setValue(f"serial/{key}", value)
