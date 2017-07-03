#!/usr/bin/python3

import logging
import textwrap
import time
import queue

import numpy

from noisicaa import node_db
from noisicaa.bindings import csound
from noisicaa.bindings import lv2

from .. import ports
from .. import node
from .. import frame
from .. import events
from .. import audio_format

logger = logging.getLogger(__name__)


class CSoundBase(node.CustomNode):
    def __init__(self, event_loop, description, name=None, id=None):
        super().__init__(event_loop, description, name, id)

        self.__csnd = None
        self.__next_csnd = queue.Queue()
        self.__buffers = {}

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

        self.__next_csnd.put(csnd)

    async def cleanup(self):
        if self.__csnd is not None:
            self.__csnd.close()
            self.__csnd = None

        while not self.__next_csnd.empty():
            csnd = self.__next_csnd.get()
            csnd.close()

        await super().cleanup()

    def connect_port(self, port_name, buf):
        if port_name not in self.outputs and port_name not in self.inputs:
            raise ValueError(port_name)

        self.__buffers[port_name] = buf

    def run(self, ctxt):
        try:
            next_csnd = self.__next_csnd.get_nowait()
        except queue.Empty:
            pass
        else:
            if self.__csnd is not None:
                self.__csnd.close()
                self.__csnd = None

            self.__csnd = next_csnd

        if self.__csnd is None:
            for port in self.outputs.values():
                if isinstance(port, (ports.AudioOutputPort, ports.ControlOutputPort)):
                    self.__buffers[port.name] = [0] * ctxt.duration
                else:
                    raise ValueError(port)

            return

        in_events = {}
        for port in self.inputs.values():
            if isinstance(port, ports.EventInputPort):
                in_events[port.name] = (
                    port.csound_instr,
                    list(lv2.wrap_atom(
                        lv2.static_mapper, self.__buffers[port.name]).events))

        pos = 0
        while pos < ctxt.duration:
            for port in self.inputs.values():
                if isinstance(port, (ports.AudioInputPort, ports.ControlInputPort)):
                    self.__csnd.set_audio_channel_data(
                        port.name,
                        self.__buffers[port.name][4*pos:4*(pos+self.__csnd.ksmps)])

                elif isinstance(port, ports.EventInputPort):
                    instr, pending_events = in_events[port.name]
                    while (len(pending_events) > 0
                           and pending_events[0].frames < (
                               pos + ctxt.sample_pos + self.__csnd.ksmps)):
                        event = pending_events.pop(0)
                        midi = event.atom.data
                        if midi[0] & 0xf0 == 0x90:
                            self.__csnd.add_score_event(
                                'i %s.%d 0 -1 %d %d' % (
                                    instr, midi[1], midi[1], midi[2]))

                        elif midi[0] & 0xf0 == 0x80:
                            self.__csnd.add_score_event(
                                'i -%s.%d 0 0 0' % (
                                    instr, midi[1]))

                        else:
                            raise NotImplementedError(
                                "Event class %s not supported" % type(event).__name__)

            for parameter in self.description.parameters:
                if parameter.param_type == node_db.ParameterType.Float:
                    self.__csnd.set_control_channel_value(
                        parameter.name, self.get_param(parameter.name))

            self.__csnd.perform()

            for port in self.outputs.values():
                if isinstance(port, (ports.AudioOutputPort, ports.ControlOutputPort)):
                    self.__buffers[port.name][4*pos:4*(pos+self.__csnd.ksmps)] = (
                        self.__csnd.get_audio_channel_data(port.name))
                else:
                    raise ValueError(port)

            pos += self.__csnd.ksmps

        assert pos == ctxt.duration


class CSoundFilter(CSoundBase):
    class_name = 'csound_filter'

    def __init__(self, event_loop, description, name=None, id=None):
        super().__init__(event_loop, description, name, id)

        self.__orchestra = description.get_parameter('orchestra').value
        self.__score = description.get_parameter('score').value

    async def setup(self):
        await super().setup()

        self.set_code(self.__orchestra, self.__score)


class CustomCSound(CSoundBase):
    class_name = 'custom_csound'

    def __init__(self, event_loop, description, name=None, id=None):
        super().__init__(event_loop, description, name, id)

        self.__orchestra_preamble = textwrap.dedent("""\
            ksmps=32
            nchnls=2
            """)

        for port_desc in description.ports:
            if (port_desc.port_type == node_db.PortType.Audio
                    and port_desc.direction == node_db.PortDirection.Input):
                self.__orchestra_preamble += textwrap.dedent("""\
                    ga{1}L chnexport "{0}/left", 1
                    ga{1}R chnexport "{0}/right", 1
                    """.format(port_desc.name, port_desc.name.title()))

            elif (port_desc.port_type == node_db.PortType.Audio
                    and port_desc.direction == node_db.PortDirection.Output):
                self.__orchestra_preamble += textwrap.dedent("""\
                    ga{1}L chnexport "{0}/left", 2
                    ga{1}R chnexport "{0}/right", 2
                    """.format(port_desc.name, port_desc.name.title()))

            elif (port_desc.port_type == node_db.PortType.Control
                    and port_desc.direction == node_db.PortDirection.Input):
                self.__orchestra_preamble += textwrap.dedent("""\
                    ga{1} chnexport "{0}", 1
                    """.format(port_desc.name, port_desc.name.title()))

            elif (port_desc.port_type == node_db.PortType.Control
                    and port_desc.direction == node_db.PortDirection.Output):
                self.__orchestra_preamble += textwrap.dedent("""\
                    ga{1} chnexport "{0}", 2
                    """.format(port_desc.name, port_desc.name.title()))

            elif (port_desc.port_type == node_db.PortType.Events
                    and port_desc.direction == node_db.PortDirection.Input):
                pass

            else:
                raise ValueError(port_desc)

        self.__orchestra = self.get_param('orchestra')
        self.__score = self.get_param('score')

    async def setup(self):
        await super().setup()

        self.set_code(self.__orchestra_preamble + self.__orchestra, self.__score)

    def set_param(self, **kwargs):
        super().set_param(**kwargs)

        reinit = False
        if 'orchestra' in kwargs:
            self.__orchestra = kwargs.get('orchestra')
            reinit = True
        if 'score' in kwargs:
            self.__score = kwargs.get('score')
            reinit = True

        if reinit:
            self.set_code(self.__orchestra_preamble + self.__orchestra, self.__score)
