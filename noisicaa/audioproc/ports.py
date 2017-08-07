#!/usr/bin/python3

import logging

from .exceptions import Error
from .vm import buffers

logger = logging.getLogger(__name__)


UNSET = object()


class Port(object):
    def __init__(self, name):
        self._name = name
        self.owner = None

    def __str__(self):
        return '<%s %s:%s>' % (
            type(self).__name__,
            self.owner.id if self.owner is not None else 'None',
            self.name)

    @property
    def name(self):
        return self._name

    @property
    def pipeline(self):
        return self.owner.pipeline

    @property
    def buf_name(self):
        return '%s:%s' % (self.owner.id, self._name)

    def get_buf_type(self, compiler):
        raise NotImplementedError(type(self).__name__)

    def set_prop(self):
        pass


class InputPort(Port):
    def __init__(self, name):
        super().__init__(name)
        self.inputs = []

    def connect(self, port):
        self.check_port(port)
        self.inputs.append(port)

    def disconnect(self, port):
        assert port in self.inputs, port
        self.inputs.remove(port)

    def check_port(self, port):
        if not isinstance(port, OutputPort):
            raise Error("Can only connect to OutputPort")


class OutputPort(Port):
    def __init__(self, name, bypass_port=None):
        super().__init__(name)
        self._muted = False
        self._bypass = False
        self._bypass_port = bypass_port

    @property
    def muted(self):
        return self._muted

    @muted.setter
    def muted(self, value):
        self._muted = bool(value)

    @property
    def bypass_port(self):
        return self._bypass_port

    @property
    def bypass(self):
        return self._bypass

    @bypass.setter
    def bypass(self, value):
        assert self._bypass_port is not None
        self._bypass = bool(value)

    def set_prop(self, muted=None, bypass=None, **kwargs):
        super().set_prop(**kwargs)
        if muted is not None:
            self.muted = muted
        if bypass is not None:
            self.bypass = bypass


class AudioInputPort(InputPort):
    def check_port(self, port):
        super().check_port(port)
        if not isinstance(port, AudioOutputPort):
            raise Error("Can only connect to AudioOutputPort")

    def get_buf_type(self, compiler):
        return buffers.FloatArray(compiler.frame_size)


class AudioOutputPort(OutputPort):
    def __init__(self, name, drywet_port=None, **kwargs):
        super().__init__(name, **kwargs)

        self._volume = 100.0
        self._drywet = 0.0
        self._drywet_port = drywet_port

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, value):
        value = float(value)
        if value < 0.0:
            raise ValueError("Invalid volume.")
        self._volume = float(value)

    @property
    def drywet_port(self):
        return self._drywet_port

    @property
    def drywet(self):
        return self._drywet

    @drywet.setter
    def drywet(self, value):
        value = float(value)
        if value < -100.0 or value > 100.0:
            raise ValueError("Invalid dry/wet value.")
        self._drywet = float(value)

    def set_prop(self, volume=None, drywet=None, **kwargs):
        super().set_prop(**kwargs)
        if volume is not None:
            self.volume = volume
        if drywet is not None:
            self.drywet = drywet

    def get_buf_type(self, compiler):
        return buffers.FloatArray(compiler.frame_size)


class ARateControlInputPort(InputPort):
    def check_port(self, port):
        super().check_port(port)
        if not isinstance(port, ARateControlOutputPort):
            raise Error("Can only connect to ARateControlOutputPort")

    def get_buf_type(self, compiler):
        return buffers.FloatArray(compiler.frame_size)


class ARateControlOutputPort(OutputPort):
    def get_buf_type(self, compiler):
        return buffers.FloatArray(compiler.frame_size)


class KRateControlInputPort(InputPort):
    def check_port(self, port):
        super().check_port(port)
        if not isinstance(port, KRateControlOutputPort):
            raise Error("Can only connect to KRateControlOutputPort")

    def get_buf_type(self, compiler):
        return buffers.Float()


class KRateControlOutputPort(OutputPort):
    def get_buf_type(self, compiler):
        return buffers.Float()


class EventInputPort(InputPort):
    def __init__(self, name, csound_instr='1'):
        super().__init__(name)
        self.csound_instr = csound_instr

    def check_port(self, port):
        super().check_port(port)
        if not isinstance(port, EventOutputPort):
            raise Error("Can only connect to EventOutputPort")

    def get_buf_type(self, compiler):
        return buffers.AtomData(10240)


class EventOutputPort(OutputPort):
    def get_buf_type(self, compiler):
        return buffers.AtomData(10240)
