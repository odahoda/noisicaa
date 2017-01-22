#!/usr/bin/python3

import unittest

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


if __name__ == '__main__':
    unittest.main()
