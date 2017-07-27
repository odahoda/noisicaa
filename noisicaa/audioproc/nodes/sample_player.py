#!/usr/bin/python3

import logging
import queue
import time
import textwrap

from noisicaa import node_db
from ..exceptions import SetupError
from ..ports import EventInputPort, AudioOutputPort
from ..events import NoteOnEvent, NoteOffEvent
from . import csound

logger = logging.getLogger(__name__)


class SamplePlayer(csound.CSoundBase):
    class_name = 'sample_player'

    def __init__(self, *, sample_path, **kwargs):
        description = node_db.UserNodeDescription(
            display_name="Sample Player",
            node_cls='sample_player',
            ports=[
                node_db.EventPortDescription(
                    name='in',
                    direction=node_db.PortDirection.Input),
                node_db.AudioPortDescription(
                    name='out:left',
                    direction=node_db.PortDirection.Output),
                node_db.AudioPortDescription(
                    name='out:right',
                    direction=node_db.PortDirection.Output),
            ])

        super().__init__(description=description, **kwargs)

        self._sample_path = sample_path

    def setup(self):
        super().setup()

        orchestra = textwrap.dedent("""\
            ksmps=32
            nchnls=2

            gaOutL chnexport "out:left", 2
            gaOutR chnexport "out:right", 2

            instr 1
              iPitch = p4
              iVelocity = p5

              iFreq = cpsmidinn(iPitch)
              iVolume = -20 * log10(127^2 / iVelocity^2)

              iChannels = ftchnls(1)

              if (iChannels == 1) then
                aOut loscil3 0.5 * db(iVolume), iFreq, 1, 261.626, 0
                gaOutL = gaOutL + aOut
                gaOutR = gaOutR + aOut
              elseif (iChannels == 2) then
                aOutL, aOutR loscil3 0.5 * db(iVolume), iFreq, 1, 220, 0
                gaOutL = gaOutL + aOutL
                gaOutR = gaOutR + aOutR
              endif
            endin
            """)

        score = textwrap.dedent("""\
            f 1 0 0 1 "{path}" 0 0 0
            """).format(path=self._sample_path)

        self.set_code(orchestra, score)
