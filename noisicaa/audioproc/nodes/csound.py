#!/usr/bin/python3

import logging
import textwrap
import time
import queue

import numpy

from noisicaa import node_db

from .. import csound
from .. import ports
from .. import node
from .. import frame
from .. import events
from .. import audio_format

logger = logging.getLogger(__name__)


class CSoundBase(node.CustomNode):
    def __init__(self, event_loop, description, name=None, id=None):
        super().__init__(event_loop, description, name, id)

        self._csnd = None
        self._next_csnd = queue.Queue()

    def set_code(self, orchestra, score):
        csnd = csound.CSound()
        try:
            csnd.set_orchestra(orchestra)
        except csound.CSoundError as exc:
            logger.error("Exception when setting orchestra: %s", exc)
            csnd.close()
            return

        try:
            csnd.set_score(score)
        except csound.CSoundError as exc:
            logger.error("Exception when setting score: %s", exc)
            csnd.close()
            return

        self._next_csnd.put(csnd)

    async def cleanup(self):
        if self._csnd is not None:
            self._csnd.close()
            self._csnd = None

        while not self._next_csnd.empty():
            csnd = self._next_csnd.get()
            csnd.close()

        await super().cleanup()

    def run(self, ctxt):
        try:
            next_csnd = self._next_csnd.get_nowait()
        except queue.Empty:
            pass
        else:
            if self._csnd is not None:
                self._csnd.close()
                self._csnd = None

            self._csnd = next_csnd

        if self._csnd is None:
            for port in self.outputs.values():
                if isinstance(port, ports.AudioOutputPort):
                    port.frame.resize(ctxt.duration)
                    port.frame.clear()
                elif isinstance(port, ports.ControlOutputPort):
                    port.frame.resize(ctxt.duration)
                    port.frame.fill(0.0)
                else:
                    raise ValueError(port)

            return

        in_samples = {}
        in_control = {}
        in_events = {}
        for port in self.inputs.values():
            if isinstance(port, ports.AudioInputPort):
                assert len(port.frame) == ctxt.duration
                in_samples[port.name] = port.frame.samples
            elif isinstance(port, ports.ControlInputPort):
                in_control[port.name] = port.frame
            elif isinstance(port, ports.EventInputPort):
                in_events[port.name] = (port.csound_instr, list(port.events))
            else:
                raise ValueError(port)

        out_samples = {}
        out_control = {}
        for port in self.outputs.values():
            if isinstance(port, ports.AudioOutputPort):
                port.frame.resize(ctxt.duration)
                out_samples[port.name] = port.frame.samples
            elif isinstance(port, ports.ControlOutputPort):
                port.frame.resize(ctxt.duration)
                out_control[port.name] = port.frame
            else:
                raise ValueError(port)

        pos = 0
        while pos < ctxt.duration:
            for port_name, samples in in_samples.items():
                self._csnd.set_audio_channel_data(
                    '%s/left' % port_name,
                    samples[0][pos:pos+self._csnd.ksmps])
                self._csnd.set_audio_channel_data(
                    '%s/right' % port_name,
                    samples[1][pos:pos+self._csnd.ksmps])

            for port_name, samples in in_control.items():
                self._csnd.set_audio_channel_data(
                    '%s' % port_name,
                    samples[pos:pos+self._csnd.ksmps])

            for port_name, (instr, pending_events) in in_events.items():
                while (len(pending_events) > 0
                       and pending_events[0].sample_pos < (
                           pos + ctxt.sample_pos + self._csnd.ksmps)):
                    event = pending_events.pop(0)
                    if isinstance(event, events.NoteOnEvent):
                        self._csnd.add_score_event(
                            'i %s.%d 0 -1 %d %d' % (
                                instr, event.note.midi_note, event.note.midi_note, event.volume))
                    elif isinstance(event, events.NoteOffEvent):
                        self._csnd.add_score_event(
                            'i -%s.%d 0 0 0' % (
                                instr, event.note.midi_note))
                    else:
                        raise NotImplementedError(
                            "Event class %s not supported" % type(event).__name__)

            for parameter in self.description.parameters:
                if parameter.param_type == node_db.ParameterType.Float:
                    self._csnd.set_control_channel_value(
                        parameter.name, self.get_param(parameter.name))

            self._csnd.perform()

            for port_name, samples in out_samples.items():
                samples[0][pos:pos+self._csnd.ksmps] = (
                    self._csnd.get_audio_channel_data(
                        '%s/left' % port_name))
                samples[1][pos:pos+self._csnd.ksmps] = (
                    self._csnd.get_audio_channel_data(
                        '%s/right' % port_name))

            for port_name, samples in out_control.items():
                samples[pos:pos+self._csnd.ksmps] = (
                    self._csnd.get_audio_channel_data(
                        '%s' % port_name))

            pos += self._csnd.ksmps

        assert pos == ctxt.duration


class CSoundFilter(CSoundBase):
    class_name = 'csound_filter'

    def __init__(self, event_loop, description, name=None, id=None):
        super().__init__(event_loop, description, name, id)

        self._orchestra = description.get_parameter('orchestra').value
        self._score = description.get_parameter('score').value

    async def setup(self):
        await super().setup()

        self.set_code(self._orchestra, self._score)


class CustomCSound(CSoundBase):
    class_name = 'custom_csound'

    def __init__(self, event_loop, description, name=None, id=None):
        super().__init__(event_loop, description, name, id)

        self._orchestra_preamble = textwrap.dedent("""\
            ksmps=32
            nchnls=2
            """)

        for port_desc in description.ports:
            if (port_desc.port_type == node_db.PortType.Audio
                    and port_desc.direction == node_db.PortDirection.Input):
                self._orchestra_preamble += textwrap.dedent("""\
                    ga{1}L chnexport "{0}/left", 1
                    ga{1}R chnexport "{0}/right", 1
                    """.format(port_desc.name, port_desc.name.title()))

            elif (port_desc.port_type == node_db.PortType.Audio
                    and port_desc.direction == node_db.PortDirection.Output):
                self._orchestra_preamble += textwrap.dedent("""\
                    ga{1}L chnexport "{0}/left", 2
                    ga{1}R chnexport "{0}/right", 2
                    """.format(port_desc.name, port_desc.name.title()))

            elif (port_desc.port_type == node_db.PortType.Control
                    and port_desc.direction == node_db.PortDirection.Input):
                self._orchestra_preamble += textwrap.dedent("""\
                    ga{1} chnexport "{0}", 1
                    """.format(port_desc.name, port_desc.name.title()))

            elif (port_desc.port_type == node_db.PortType.Control
                    and port_desc.direction == node_db.PortDirection.Output):
                self._orchestra_preamble += textwrap.dedent("""\
                    ga{1} chnexport "{0}", 2
                    """.format(port_desc.name, port_desc.name.title()))

            elif (port_desc.port_type == node_db.PortType.Events
                    and port_desc.direction == node_db.PortDirection.Input):
                pass

            else:
                raise ValueError(port_desc)

        self._orchestra = self.get_param('orchestra')
        self._score = self.get_param('score')

    async def setup(self):
        await super().setup()

        self.set_code(self._orchestra_preamble + self._orchestra, self._score)

    def set_param(self, **kwargs):
        super().set_param(**kwargs)

        reinit = False
        if 'orchestra' in kwargs:
            self._orchestra = kwargs.get('orchestra')
            reinit = True
        if 'score' in kwargs:
            self._score = kwargs.get('score')
            reinit = True

        if reinit:
            self.set_code(self._orchestra_preamble + self._orchestra, self._score)
