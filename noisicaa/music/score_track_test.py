#!/usr/bin/python3

import unittest

from noisicaa.bindings import lv2
from noisicaa.bindings import sratom
from noisicaa import audioproc

from . import event_set
from . import pitch
from . import project
from . import score_track


class EventSetConnectorTest(unittest.TestCase):
    def test_foo(self):
        pr = project.BaseProject.make_demo()
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


class ScoreEntitySourceTest(unittest.TestCase):
    def test_foo(self):
        pr = project.BaseProject.make_demo()
        tr = pr.sheets[0].master_group.tracks[0]
        src = score_track.ScoreEntitySource(tr)

        frdata = audioproc.FrameData()
        frdata.sample_pos = 0
        frdata.entities = {}

        src.get_entities(frdata, 0, 1024, 0)

        buf = frdata.entities['track:%s' % tr.id].buf

        turtle = sratom.atom_to_turtle(lv2.static_mapper, buf)
        print(turtle)


if __name__ == '__main__':
    unittest.main()
