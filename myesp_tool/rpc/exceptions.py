

class RPCError(Exception):
    pass

class RPCPktError(Exception):
    pass


class RPCInvalidPktError(RPCPktError):
    """无效包异常，当包的 magic 或其他字段不合法时抛出"""
    pass


class RPCIncompletePktError(RPCPktError):
    """不完整包异常，当包的实际长度与期望长度不匹配时抛出"""
    pass
