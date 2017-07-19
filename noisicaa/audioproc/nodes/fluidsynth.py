#!/usr/bin/python3

import logging
import queue
import time

from noisicaa import node_db

from noisicaa.bindings import fluidsynth
from noisicaa.bindings import lv2
from .. import node

logger = logging.getLogger(__name__)


class FluidSynthSource(node.CustomNode):
    class_name = 'fluidsynth'

    master_synth = fluidsynth.Synth()
    master_sfonts = {}

    def __init__(self, *, soundfont_path, bank, preset, **kwargs):
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

        super().__init__(description=description, **kwargs)

        self.__soundfont_path = soundfont_path
        self.__bank = bank
        self.__preset = preset

        self.__synth = None
        self.__sfont = None
        self.__sfid = None

        self.__in = None
        self.__out_left = None
        self.__out_right = None

    def setup(self):
        super().setup()

        assert self.__synth is None

        self.__settings = fluidsynth.Settings()
        self.__settings.synth_gain = 0.5
        self.__settings.synth_sample_rate = 44100  # TODO: get from pipeline
        self.__synth = fluidsynth.Synth(self.__settings)
        try:
            sfont = self.master_sfonts[self.__soundfont_path]
        except KeyError:
            logger.info(
                "Adding new soundfont %s to master synth.",
                self.__soundfont_path)
            master_sfid = self.master_synth.sfload(self.__soundfont_path)
            sfont = self.master_synth.get_sfont(master_sfid)
            self.master_sfonts[self.__soundfont_path] = sfont

        logger.debug("Using soundfont %s", sfont.id)
        self.__sfid = self.__synth.add_sfont(sfont)
        logger.debug("Soundfont id=%s", self.__sfid)
        self.__sfont = sfont

        self.__synth.system_reset()
        self.__synth.program_select(
            0, self.__sfid, self.__bank, self.__preset)

    def cleanup(self):
        super().cleanup()

        if self.__synth is not None:
            self.__synth.system_reset()
            if self.__sfont is not None:
                # TODO: This call spits out a ton of "CRITICAL **:
                # fluid_synth_sfont_unref: assertion 'sfont_info != NULL' failed"
                # messages on STDERR
                self.__synth.remove_sfont(self.__sfont)
                self.__sfont = None
            self.__synth = None

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
        seq = lv2.wrap_atom(lv2.static_mapper, self.__in)
        segment_start = 0
        bytes_written = 0
        for event in seq.events:
            if event.frames != -1:
                assert 0 <= event.frames < ctxt.duration, (
                    event.frames, ctxt.duration)
                esample_pos = event.frames
            else:
                esample_pos = 0

            if esample_pos >= segment_start:
                segmentl, segmentr = self.__synth.get_samples(
                    esample_pos - segment_start)
                self.__out_left[bytes_written:bytes_written+len(segmentl)] = segmentl
                self.__out_right[bytes_written:bytes_written+len(segmentl)] = segmentr
                segment_start = esample_pos
                bytes_written += len(segmentl)

            midi = event.atom.data
            if midi[0] & 0xf0 == 0x90:
                self.__synth.noteon(0, midi[1], midi[2])
            elif midi[0] & 0xf0 == 0x80:
                self.__synth.noteoff(0, midi[1])
            else:
                raise NotImplementedError(
                    "Event class %s not supported" % type(event).__name__)

        if segment_start < ctxt.duration:
            segmentl, segmentr = self.__synth.get_samples(
                ctxt.duration - segment_start)
            self.__out_left[bytes_written:bytes_written+len(segmentl)] = segmentl
            self.__out_right[bytes_written:bytes_written+len(segmentl)] = segmentr
