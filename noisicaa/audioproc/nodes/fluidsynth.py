#!/usr/bin/python3

import logging
import queue
import time

from noisicaa import node_db

from ..resample import (Resampler,
                        AV_CH_LAYOUT_STEREO,
                        AV_SAMPLE_FMT_S16,
                        AV_SAMPLE_FMT_FLT)
from .. import libfluidsynth
from ..exceptions import SetupError
from ..ports import EventInputPort, AudioOutputPort
from .. import node
from ..events import NoteOnEvent, NoteOffEvent, EndOfStreamEvent
from ..frame import Frame
from .. import audio_format

logger = logging.getLogger(__name__)


class FluidSynthSource(node.CustomNode):
    class_name = 'fluidsynth'

    master_synth = libfluidsynth.Synth()
    master_sfonts = {}

    def __init__(self, event_loop, name=None, id=None,
                 soundfont_path=None, bank=None, preset=None):
        description = node_db.SystemNodeDescription(
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

        super().__init__(event_loop, description, name, id)

        self._soundfont_path = soundfont_path
        self._bank = bank
        self._preset = preset

        self._synth = None
        self._sfont = None
        self._sfid = None
        self._resampler = None

        self.__in = None
        self.__out_left = None
        self.__out_right = None

    async def setup(self):
        await super().setup()

        assert self._synth is None

        self._synth = libfluidsynth.Synth(gain=0.5)
        try:
            sfont = self.master_sfonts[self._soundfont_path]
        except KeyError:
            logger.info(
                "Adding new soundfont %s to master synth.",
                self._soundfont_path)
            master_sfid = self.master_synth.sfload(self._soundfont_path)
            if master_sfid == -1:
                raise SetupError(
                    "Failed to load SoundFont %s" % self._soundfont_path)
            sfont = self.master_synth.get_sfont(master_sfid)
            self.master_sfonts[self._soundfont_path] = sfont

        logger.debug("Using soundfont %s", sfont)
        self._sfid = self._synth.add_sfont(sfont)
        logger.debug("Soundfont id=%s", self._sfid)
        if self._sfid == -1:
            raise SetupError(
                "Failed to add SoundFont %s" % self._soundfont_path)
        self._sfont = sfont

        self._synth.system_reset()
        self._synth.program_select(
            0, self._sfid, self._bank, self._preset)

        self._resampler = Resampler(
            AV_CH_LAYOUT_STEREO, AV_SAMPLE_FMT_S16, 44100,
            AV_CH_LAYOUT_STEREO, AV_SAMPLE_FMT_FLT, 44100)

    async def cleanup(self):
        await super().cleanup()

        self._resampler = None
        if self._synth is not None:
            self._synth.system_reset()
            if self._sfont is not None:
                # TODO: This call spits out a ton of "CRITICAL **:
                # fluid_synth_sfont_unref: assertion 'sfont_info != NULL' failed"
                # messages on STDERR
                self._synth.remove_sfont(self._sfont)
                self._sfont = None
            self._synth.delete()
            self._synth = None

    def connect_port(self, port_name, buf):
        if port_name == 'in':
            self.__in = buf
        elif port_name == 'out:left':
            self.__out_left = buf
        elif port_name == 'out:right':
            self.__out_right = buf
        else:
            raise ValueError(port_name)

    def run(self, ctxt):
        pass  # TODO
        # samples = bytes()
        # tp = ctxt.sample_pos

        # for event in self.inputs['in'].events:
        #     if event.sample_pos != -1:
        #         assert ctxt.sample_pos <= event.sample_pos < ctxt.sample_pos + ctxt.duration, (
        #             ctxt.sample_pos, event.sample_pos, ctxt.sample_pos + ctxt.duration)
        #         esample_pos = event.sample_pos
        #     else:
        #         esample_pos = ctxt.sample_pos

        #     if esample_pos > tp:
        #         samples += bytes(
        #             self._synth.get_samples(esample_pos - tp))
        #         tp = esample_pos

        #     if isinstance(event, NoteOnEvent):
        #         self._synth.noteon(
        #             0, event.note.midi_note, event.volume)
        #     elif isinstance(event, NoteOffEvent):
        #         self._synth.noteoff(
        #             0, event.note.midi_note)
        #     elif isinstance(event, EndOfStreamEvent):
        #         break
        #     else:
        #         raise NotImplementedError(
        #             "Event class %s not supported" % type(event).__name__)

        # if tp < ctxt.sample_pos + ctxt.duration:
        #     samples += bytes(
        #         self._synth.get_samples(
        #             ctxt.sample_pos + ctxt.duration - tp))

        # samples = self._resampler.convert(
        #     samples, len(samples) // 4)

        # output_port = self.outputs['out']
        # af = output_port.frame.audio_format
        # frame = Frame(af, 0, set())
        # frame.append_samples(
        #     samples, len(samples) // (
        #         # pylint thinks that frame.audio_format is a class object.
        #         # pylint: disable=E1101
        #         af.num_channels * af.bytes_per_sample))
        # assert len(frame) == ctxt.duration

        # output_port.frame.resize(ctxt.duration)
        # output_port.frame.copy_from(frame)
