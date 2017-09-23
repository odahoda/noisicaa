#!/usr/bin/python3

import unittest

import asynctest

from noisicaa.bindings import lv2
from noisicaa.bindings import sratom
from noisicaa import audioproc
from noisicaa.node_db.private import db as node_db

from . import event_set
from . import pitch
from . import player
from . import project
from . import score_track


class NodeDB(object):
    def __init__(self):
        self.db = node_db.NodeDB()

    async def setup(self):
        self.db.setup()

    async def cleanup(self):
        self.db.cleanup()

    def get_node_description(self, uri):
        return self.db._nodes[uri]



class EventSetConnectorTest(asynctest.TestCase):
    async def setUp(self):
        self.node_db = NodeDB()
        await self.node_db.setup()

    async def tearDown(self):
        await self.node_db.cleanup()

    def test_foo(self):
        pr = project.BaseProject.make_demo(node_db=self.node_db)
        tr = pr.sheets[0].master_group.tracks[0]
        es = event_set.EventSet()
        connector = score_track.EventSetConnector(tr, es)
        try:
            print('\n'.join(str(e) for e in sorted(es.get_intervals(0, 1000))))
            print()
            pr.sheets[0].property_track.insert_measure(1)
            tr.insert_measure(1)
            print('\n'.join(str(e) for e in sorted(es.get_intervals(0, 1000))))
            print()
            m = tr.measure_list[1].measure
            m.notes.append(score_track.Note(pitches=[pitch.Pitch('D#4')]))
            print('\n'.join(str(e) for e in sorted(es.get_intervals(0, 1000))))
        finally:
            connector.close()


class ScoreBufferSourceTest(asynctest.TestCase):
    async def setUp(self):
        self.node_db = NodeDB()
        await self.node_db.setup()

    async def tearDown(self):
        await self.node_db.cleanup()

    async def test_foo(self):
        pr = project.BaseProject.make_demo(node_db=self.node_db)
        tr = pr.sheets[0].master_group.tracks[0]
        src = score_track.ScoreBufferSource(tr)

        buffers = {}
        ctxt = player.GetBuffersContext(buffers=buffers, block_size=1024)
        ctxt.sample_pos = 0
        ctxt.length = 1024
        src.get_buffers(ctxt)

        buf = buffers['track:%s' % tr.id]

        turtle = sratom.atom_to_turtle(lv2.static_mapper, buf.data)
        print(turtle)


if __name__ == '__main__':
    unittest.main()
