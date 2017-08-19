#!/usr/bin/python3

import textwrap
import unittest

from . import csound


class CSoundTest(unittest.TestCase):
    def test_version(self):
        self.assertEqual(csound.__version__, '6.08.0')

    def test_constructor(self):
        csnd = csound.CSound()
        csnd.close()

    def test_play(self):
        orc = textwrap.dedent("""\
            ksmps=32
            nchnls=2

            gaOutL chnexport "OutL", 2
            gaOutR chnexport "OutR", 2

            instr 1
                gaOutL vco2 0.5, p4
                gaOutR = 0
                    outs gaOutL, gaOutR
            endin
        """)

        csnd = csound.CSound()
        try:
            csnd.set_orchestra(orc)
            self.assertEqual(csnd.ksmps, 32)
            self.assertEqual(len(csnd.channels), 2)

            for i in range(10):
                if i == 2:
                    csnd.add_score_event(b'i1 0 1 440')
                csnd.perform()
                print(csnd.get_audio_channel_data('OutL'))

        finally:
            csnd.close()


if __name__ == '__main__':
    unittest.main()
