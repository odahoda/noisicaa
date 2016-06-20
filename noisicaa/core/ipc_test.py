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
            server.add_command_handler('foo', lambda: None)
            server.add_command_handler('bar', lambda: 'yo')
            server.add_command_handler('gnurz', lambda a: a + 1)

            async with ipc.Stub(self.loop, server.address) as stub:
                self.assertIsNone(await stub.call('foo'))
                self.assertEqual(await stub.call('bar'), 'yo')
                self.assertEqual(await stub.call('gnurz', 3), 4)

    async def test_remote_exception(self):
        async with ipc.Server(self.loop, name='test') as server:
            server.add_command_handler('foo', lambda: 1/0)
            async with ipc.Stub(self.loop, server.address) as stub:
                with self.assertRaises(ipc.RemoteException):
                    await stub.call('foo')

    async def test_async_handler(self):
        async with ipc.Server(self.loop, name='test') as server:
            async def handler(arg):
                return arg + 1
            server.add_command_handler('foo', handler)

            async with ipc.Stub(self.loop, server.address) as stub:
                self.assertEqual(await stub.call('foo', 3), 4)


if __name__ == '__main__':
    unittest.main()
