#!/usr/bin/python3


class NodeDBProcessBase(object):
    async def setup(self):
        await super().setup()

        self.server.add_command_handler(
            'START_SESSION', self.handle_start_session)
        self.server.add_command_handler(
            'END_SESSION', self.handle_end_session)
        self.server.add_command_handler('SHUTDOWN', self.handle_shutdown)
        self.server.add_command_handler(
            'START_SCAN', self.handle_start_scan)

    def handle_start_session(self, client_address, flags):
        raise NotImplementedError

    def handle_end_session(self, session_id):
        raise NotImplementedError

    async def handle_shutdown(self):
        raise NotImplementedError

    async def handle_start_scan(self, session_id):
        raise NotImplementedError
