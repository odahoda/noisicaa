#!/usr/bin/python3

from libc.stdint cimport uint8_t, uint32_t
from libc cimport string

import logging
import queue
import time

from noisicaa import node_db

from noisicaa.bindings cimport fluidsynth
from noisicaa.bindings.lv2 cimport atom
from .. cimport node

logger = logging.getLogger(__name__)


cdef class FluidSynthSource(node.CustomNode):
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

        self.__in = None
        self.__out_left = None
        self.__out_right = None

        self.__mapper = urid.get_static_mapper()
        self.__sequence_urid = self.__mapper.map(
            b'http://lv2plug.in/ns/ext/atom#Sequence')
        self.__midi_event_urid = self.__mapper.map(
            b'http://lv2plug.in/ns/ext/midi#MidiEvent')

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
        sfid = self.__synth.add_sfont(sfont)
        logger.debug("Soundfont id=%s", sfid)
        self.__sfont = sfont

        self.__synth.system_reset()
        self.__synth.program_select(0, sfid, self.__bank, self.__preset)

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

    cdef int connect_port(self, port_name, buf) except -1:
        if port_name == 'in':
            self.__in = buf
        elif port_name == 'out:left':
            self.__out_left = buf
        elif port_name == 'out:right':
            self.__out_right = buf
        else:
            raise ValueError(port_name)
        return 0

    cdef int run(self, ctxt) except -1:
        cdef:
            atom.LV2_Atom_Sequence* seq
            atom.LV2_Atom_Event* event
            uint32_t segment_start
            uint32_t bytes_written
            uint32_t esample_pos
            uint8_t* midi
            float* out_left
            float* out_right
            uint32_t num_samples
            uint8_t event_class
            uint32_t frame_size

        frame_size = ctxt.duration

        with nogil:
            seq = <atom.LV2_Atom_Sequence*>self.__in.data
            if seq.atom.type != self.__sequence_urid:
                with gil:
                    raise TypeError(
                        "Excepted sequence, got %s"
                        % self.__mapper.unmap(seq.atom.type))
            event = atom.lv2_atom_sequence_begin(&seq.body)

            segment_start = 0
            out_left = <float*>self.__out_left.data
            out_right = <float*>self.__out_right.data
            while not atom.lv2_atom_sequence_is_end(&seq.body, seq.atom.size, event):
                if event.body.type != self.__midi_event_urid:
                    with gil:
                        raise TypeError(
                            "Excepted MidiEvent, got %s"
                            % self.__mapper.unmap(event.body.type))

                if event.time.frames != -1:
                    if not (0 <= event.time.frames < frame_size):
                        with gil:
                            raise ValueError(
                                "Event timestamp %d out of bounds [0,%d]"
                                % (event.time.frames, frame_size))

                    esample_pos = event.time.frames
                else:
                    esample_pos = 0

                if esample_pos >= segment_start:
                    num_samples = esample_pos - segment_start
                    self.__synth.get_samples_into(num_samples, out_left, out_right)
                    segment_start = esample_pos
                    out_left += num_samples
                    out_right += num_samples

                midi = (<uint8_t*>&event.body) + sizeof(atom.LV2_Atom)
                event_class = (midi[0] & 0xf0) >> 4
                if event_class == 0x9:
                    self.__synth.noteon(0, midi[1], midi[2])
                elif event_class == 0x8:
                    self.__synth.noteoff(0, midi[1])
                else:
                    with gil:
                        raise NotImplementedError(
                            "Event class %x not supported" % event_class)

                event = atom.lv2_atom_sequence_next(event)

            if segment_start < frame_size:
                num_samples = frame_size - segment_start
                self.__synth.get_samples_into(num_samples, out_left, out_right)

        return 0
