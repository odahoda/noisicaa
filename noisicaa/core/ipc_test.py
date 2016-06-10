#!/usr/bin/python3

import unittest

import asynctest

from . import ipc


class IPCTest(asynctest.TestCase):
    async def test_ping(self):
        async with ipc.Server(self.loop, name='test') as server:
            async with ipc.Stub(self.loop, server.address) as stub:
                await stub.ping()
                await stub.ping()
                await stub.ping()

            async with ipc.Stub(self.loop, server.address) as stub:
                await stub.ping()

    async def test_command(self):
        async with ipc.Server(self.loop, name='test') as server:
            server.add_command_handler('foo', lambda payload: payload)

            async with ipc.Stub(self.loop, server.address) as stub:
                self.assertIsNone(await stub.call('foo'))
                self.assertEqual(await stub.call('foo', b'12345'), b'12345')
                self.assertIsNone(await stub.call('foo'))

    async def test_remote_exception(self):
        async with ipc.Server(self.loop, name='test') as server:
            server.add_command_handler('foo', lambda payload: 1/0)
            async with ipc.Stub(self.loop, server.address) as stub:
                with self.assertRaises(ipc.RemoteException):
                    await stub.call('foo')


if __name__ == '__main__':
    unittest.main()
