
_UNSET = object()

cdef class PyBackendSettings(object):
    def __init__(self, *, ipc_address=_UNSET, block_size=128):
        if ipc_address is not _UNSET:
            self.ipc_address = ipc_address
        if block_size is not _UNSET:
            self.block_size = block_size

    cdef BackendSettings get(self):
        return self.__settings

    @property
    def ipc_address(self):
        return bytes(self.__settings.ipc_address).decode('utf-8')

    @ipc_address.setter
    def ipc_address(self, value):
        self.__settings.ipc_address = value.encode('utf-8')

    @property
    def block_size(self):
        return int(self.__settings.block_size)

    @block_size.setter
    def block_size(self, value):
        self.__settings.block_size = <uint32_t>value
