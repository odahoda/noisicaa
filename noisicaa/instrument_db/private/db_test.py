#!/usr/bin/python3

import asyncio
import threading
import time
import unittest

import asynctest

from . import db


class NodeDBTest(asynctest.TestCase):
    async def test_foo(self):
        complete = asyncio.Event()
        def state_listener(state, *args):
            if state == 'complete':
                complete.set()
            print(state, args)

        instdb = db.InstrumentDB(self.loop, '/tmp')
        instdb.listeners.add('scan-state', state_listener)
        try:
            instdb.setup()

            instdb.start_scan(['/usr/share/sounds/sf2/'], False)
            self.assertTrue(await complete.wait())

        finally:
            instdb.cleanup()


if __name__ == '__main__':
    unittest.main()
