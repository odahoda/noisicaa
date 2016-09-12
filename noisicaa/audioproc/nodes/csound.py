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
from .. import node_types
from .. import frame
from .. import events

logger = logging.getLogger(__name__)


class CSoundBase(node.Node):
    def __init__(self, event_loop, name=None, id=None):
        super().__init__(event_loop, name, id)

        self._parameters = {}
        self._csnd = None
        self._next_csnd = queue.Queue()

    def init_ports(self, description):
        port_cls_map = {
            (node_db.PortType.Audio,
             node_db.PortDirection.Input): ports.AudioInputPort,
            (node_db.PortType.Audio,
             node_db.PortDirection.Output): ports.AudioOutputPort,
            (node_db.PortType.Control,
             node_db.PortDirection.Input): ports.ControlInputPort,
            (node_db.PortType.Control,
             node_db.PortDirection.Output): ports.ControlOutputPort,
            (node_db.PortType.Events,
             node_db.PortDirection.Input): ports.EventInputPort,
            (node_db.PortType.Events,
             node_db.PortDirection.Output): ports.EventOutputPort,
        }

        for port_desc in description.ports:
            port_cls = port_cls_map[
                (port_desc.port_type, port_desc.direction)]
            kwargs = {}

            if (port_desc.direction == node_db.PortDirection.Output
                    and port_desc.port_type == node_db.PortType.Audio):
                if port_desc.bypass_port is not None:
                    kwargs['bypass_port'] = port_desc.bypass_port
                if port_desc.drywet_port is not None:
                    kwargs['drywet_port'] = port_desc.drywet_port

            if (port_desc.direction == node_db.PortDirection.Input
                    and port_desc.port_type == node_db.PortType.Events):
                kwargs['csound_instr'] = port_desc.csound_instr

            port = port_cls(port_desc.name, **kwargs)
            if port_desc.direction == node_db.PortDirection.Input:
                self.add_input(port)
            else:
                self.add_output(port)

    def init_parameters(self, description):
        for parameter in description.parameters:
            if parameter.param_type in (
                    node_db.ParameterType.Float,
                    node_db.ParameterType.String,
                    node_db.ParameterType.Text):
                self._parameters[parameter.name] = {
                    'value': parameter.default,
                    'description': parameter,
                }
            elif parameter.param_type == node_db.ParameterType.Internal:
                pass
            else:
                raise ValueError(parameter)

    def set_param(self, **kwargs):
        for parameter_name, value in kwargs.items():
            assert parameter_name in self._parameters
            parameter = self._parameters[parameter_name]['description']
            if parameter.param_type == node_db.ParameterType.Float:
                assert isinstance(value, float), type(value)
                self._parameters[parameter_name]['value'] = value
            elif parameter.param_type == node_db.ParameterType.Text:
                assert isinstance(value, str), type(value)
                self._parameters[parameter_name]['value'] = value
            else:
                raise ValueError(parameter)

    def get_param(self, parameter_name):
        return self._parameters[parameter_name]['value']

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

            for parameter in self._description.parameters:
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
    desc = node_types.NodeType()
    desc.name = 'csound_filter'
    desc.port('in', 'input', 'audio')
    desc.port('out', 'output', 'audio')

    def __init__(self, event_loop, description, name=None, id=None):
        super().__init__(event_loop, name, id)

        self._description = description

        self.init_ports(self._description)
        self.init_parameters(self._description)

        self._orchestra = self._description.get_parameter('orchestra').value
        self._score = self._description.get_parameter('score').value

    async def setup(self):
        await super().setup()

        self.set_code(self._orchestra, self._score)


class CustomCSound(CSoundBase):
    desc = node_types.NodeType()
    desc.name = 'custom_csound'
    desc.port('in', 'input', 'audio')
    desc.port('out', 'output', 'audio')

    def __init__(self, event_loop, description, name=None, id=None):
        super().__init__(event_loop, name, id)

        self._description = description

        self.init_ports(self._description)
        self.init_parameters(self._description)

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
            self._score = kwargs.get('orchestra')
            reinit = True

        if reinit:
            self.set_code(self._orchestra_preamble + self._orchestra, self._score)
