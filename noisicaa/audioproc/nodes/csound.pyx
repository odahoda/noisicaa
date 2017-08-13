#!/usr/bin/python3

from libc.stdint cimport uint8_t

import logging
import textwrap
import time
import queue

import numpy

from noisicaa import node_db
from noisicaa.bindings cimport csound
from noisicaa.bindings import csound
from noisicaa.bindings import lv2
from noisicaa.bindings.lv2 cimport atom
from noisicaa.bindings.lv2 cimport urid

from .. import ports
from .. cimport node
from .. import audio_format
from ..vm cimport buffers

logger = logging.getLogger(__name__)


cdef class CSoundBase(node.CustomNode):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

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

    def cleanup(self):
        if self.__csnd is not None:
            self.__csnd.close()
            self.__csnd = None

        while not self.__next_csnd.empty():
            csnd = self.__next_csnd.get()
            csnd.close()

        super().cleanup()

    cdef int connect_port(self, port_name, buf) except -1:
        if port_name not in self.outputs and port_name not in self.inputs:
            raise ValueError(port_name)

        self.__buffers[port_name] = buf

        return 0

    cdef int run(self, ctxt) except -1:
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
                if isinstance(port, (ports.AudioOutputPort, ports.ARateControlOutputPort)):
                    self.__buffers[port.name].clear()
                else:
                    raise ValueError(port)

            return 0

        in_events = {}
        for port in self.inputs.values():
            if isinstance(port, ports.EventInputPort):
                l = list(atom.Atom.wrap(urid.get_static_mapper(), <uint8_t*>(<buffers.Buffer>self.__buffers[port.name]).data).events)
                in_events[port.name] = (port.csound_instr, l)

        cdef int pos = 0
        while pos < ctxt.duration:
            for port in self.inputs.values():
                if isinstance(port, (ports.AudioInputPort, ports.ARateControlInputPort)):
                    self.__csnd.set_audio_channel_data(
                        port.name,
                        (<buffers.Buffer>self.__buffers[port.name]).data[4*pos:4*(pos+self.__csnd.ksmps)])

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
                if isinstance(port, (ports.AudioOutputPort, ports.ARateControlOutputPort)):
                    self.__csnd.get_audio_channel_data_into(
                        port.name,
                        (<float*>(<buffers.Buffer>self.__buffers[port.name]).data) + pos)
                else:
                    raise ValueError(port)

            pos += self.__csnd.ksmps

        assert pos == ctxt.duration
        return 0


cdef class CSoundFilter(CSoundBase):
    class_name = 'csound_filter'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.__orchestra = self.description.get_parameter('orchestra').value
        self.__score = self.description.get_parameter('score').value

    def setup(self):
        super().setup()

        self.set_code(self.__orchestra, self.__score)


cdef class CustomCSound(CSoundBase):
    class_name = 'custom_csound'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.__orchestra_preamble = textwrap.dedent("""\
            ksmps=32
            nchnls=2
            """)

        for port_desc in self.description.ports:
            if (port_desc.port_type == node_db.PortType.Audio
                    and port_desc.direction == node_db.PortDirection.Input):
                self.__orchestra_preamble += textwrap.dedent("""\
                    ga{1} chnexport "{0}", 1
                    """.format(port_desc.name, port_desc.name.title().replace(':', '')))

            elif (port_desc.port_type == node_db.PortType.Audio
                    and port_desc.direction == node_db.PortDirection.Output):
                self.__orchestra_preamble += textwrap.dedent("""\
                    ga{1} chnexport "{0}", 2
                    """.format(port_desc.name, port_desc.name.title().replace(':', '')))

            elif (port_desc.port_type == node_db.PortType.ARateControl
                    and port_desc.direction == node_db.PortDirection.Input):
                self.__orchestra_preamble += textwrap.dedent("""\
                    ga{1} chnexport "{0}", 1
                    """.format(port_desc.name, port_desc.name.title().replace(':', '')))

            elif (port_desc.port_type == node_db.PortType.ARateControl
                    and port_desc.direction == node_db.PortDirection.Output):
                self.__orchestra_preamble += textwrap.dedent("""\
                    ga{1} chnexport "{0}", 2
                    """.format(port_desc.name, port_desc.name.title().replace(':', '')))

            elif (port_desc.port_type == node_db.PortType.Events
                    and port_desc.direction == node_db.PortDirection.Input):
                pass

            else:
                raise ValueError(port_desc)

        self.__orchestra = self.get_param('orchestra')
        self.__score = self.get_param('score')

    def setup(self):
        super().setup()

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