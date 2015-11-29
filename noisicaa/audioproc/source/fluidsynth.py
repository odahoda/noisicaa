#!/usr/bin/python3

import logging
import queue
import time

from ..resample import (Resampler,
                        AV_CH_LAYOUT_STEREO,
                        AV_SAMPLE_FMT_S16,
                        AV_SAMPLE_FMT_FLT)
from .. import libfluidsynth
from ..exceptions import SetupError
from ..ports import EventInputPort, AudioOutputPort
from ..node import Node
from ..events import NoteOnEvent, NoteOffEvent

logger = logging.getLogger(__name__)


class FluidSynthSource(Node):
    master_synth = libfluidsynth.Synth()
    master_sfonts = {}

    def __init__(self, soundfont_path, bank, preset):
        super().__init__()

        self._input = EventInputPort('in')
        self.add_input(self._input)

        self._output = AudioOutputPort('out')
        self.add_output(self._output)

        self._soundfont_path = soundfont_path
        self._bank = bank
        self._preset = preset

        self._timepos = 0
        self._synth = None
        self._sfont = None
        self._sfid = None
        self._resampler = None

        self._note_queue = queue.Queue()

    # TODO: saner API for realtime playback
    def note_on(self, pitch, volume):
        #assert self.started
        self._note_queue.put((True, pitch, volume, time.time()))

    def note_off(self, pitch):
        #assert self.started
        self._note_queue.put((False, pitch, 0, time.time()))

    def setup(self):
        super().setup()

        assert self._synth is None

        self._synth = libfluidsynth.Synth(gain=0.5)
        try:
            sfont = self.master_sfonts[self._soundfont_path]
        except KeyError:
            logger.info(
                "Adding new soundfont %s to master synth.", self._soundfont_path)
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

        self._resampler = Resampler(
            AV_CH_LAYOUT_STEREO, AV_SAMPLE_FMT_S16, 44100,
            AV_CH_LAYOUT_STEREO, AV_SAMPLE_FMT_FLT, 44100)

    def cleanup(self):
        super().cleanup()

        while not self._note_queue.empty():
            self._note_queue.get()

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

    def start(self):
        super().start()
        self._timepos = 0
        while not self._note_queue.empty():
            self._note_queue.get()
        self._synth.system_reset()
        self._synth.program_select(0, self._sfid, self._bank, self._preset)

    def run(self):
        tags = set()
        while True:
            try:
                on, pitch, volume, inserted = self._note_queue.get_nowait()
            except queue.Empty:
                break
            logger.info("Pitch %s %s (%.1fms delayed)",
                        pitch,
                        "on" if on else "off",
                        1000.0 * (time.time() - inserted))
            if on:
                self._synth.noteon(0, pitch.midi_note, volume)
            else:
                self._synth.noteoff(0, pitch.midi_note)

        if self._input.is_connected:
            samples = bytes()
            tp = self._timepos

            for event in self._input.get_events(4096):
                assert self._timepos <= event.timepos < self._timepos + 4096

                if event.timepos > tp:
                    samples += bytes(
                        self._synth.get_samples(event.timepos - tp))
                    tp = event.timepos

                logger.info("Consuming event %s", event)
                if isinstance(event, NoteOnEvent):
                    self._synth.noteon(
                        0, event.note.midi_note, event.volume)
                elif isinstance(event, NoteOffEvent):
                    self._synth.noteoff(
                        0, event.note.midi_note)
                else:
                    raise NotImplementedError(
                        "Event class %s not supported" % type(event).__name__)

                tags |= event.tags

            if tp < self._timepos + 4096:
                samples += bytes(
                    self._synth.get_samples(self._timepos + 4096 - tp))
        else:
            samples = bytes(
                self._synth.get_samples(4096))

        samples = self._resampler.convert(
            samples, len(samples) // 4)

        frame = self._output.create_frame(self._timepos, tags)
        frame.append_samples(
            samples, len(samples) // (
                # pylint thinks that frame.audio_format is a class object.
                # pylint: disable=E1101
                frame.audio_format.num_channels
                * frame.audio_format.bytes_per_sample))
        self._timepos += len(frame)

        #logger.info('Node %s created %s', self.name, frame)
        self._output.add_frame(frame)
