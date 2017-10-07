#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2017, Benjamin Niemann <pink@odahoda.de>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# @end:license

import logging

from . import vm
from .exceptions import Error

logger = logging.getLogger(__name__)


UNSET = object()


class Port(object):
    def __init__(self, *, description):
        self.__description = description
        self.owner = None

    def __str__(self):
        return '<%s %s:%s>' % (
            type(self).__name__,
            self.owner.id if self.owner is not None else 'None',
            self.name)

    @property
    def description(self):
        return self.__description

    @property
    def name(self):
        return self.__description.name

    @property
    def pipeline(self):
        return self.owner.pipeline

    @property
    def buf_name(self):
        return '%s:%s' % (self.owner.id, self.__description.name)

    def get_buf_type(self):
        raise NotImplementedError(type(self).__name__)

    def set_prop(self):
        pass


class InputPort(Port):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
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
    def __init__(self, *, bypass_port=None, **kwargs):
        super().__init__(**kwargs)
        self._bypass = False
        self._bypass_port = bypass_port

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

    def set_prop(self, bypass=None, **kwargs):
        super().set_prop(**kwargs)
        if bypass is not None:
            self.bypass = bypass


class AudioInputPort(InputPort):
    def check_port(self, port):
        super().check_port(port)
        if not isinstance(port, AudioOutputPort):
            raise Error("Can only connect to AudioOutputPort")

    def get_buf_type(self):
        return vm.FloatAudioBlock()


class AudioOutputPort(OutputPort):
    def __init__(self, *, drywet_port=None, **kwargs):
        super().__init__(**kwargs)

        self._drywet = 0.0
        self._drywet_port = drywet_port

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

    def set_prop(self, drywet=None, **kwargs):
        super().set_prop(**kwargs)
        if drywet is not None:
            self.drywet = drywet

    def get_buf_type(self):
        return vm.FloatAudioBlock()


class ARateControlInputPort(InputPort):
    def check_port(self, port):
        super().check_port(port)
        if not isinstance(port, ARateControlOutputPort):
            raise Error("Can only connect to ARateControlOutputPort")

    def get_buf_type(self):
        return vm.FloatAudioBlock()


class ARateControlOutputPort(OutputPort):
    def get_buf_type(self):
        return vm.FloatAudioBlock()


class KRateControlInputPort(InputPort):
    def check_port(self, port):
        super().check_port(port)
        if not isinstance(port, KRateControlOutputPort):
            raise Error("Can only connect to KRateControlOutputPort")

    def get_buf_type(self):
        return vm.Float()


class KRateControlOutputPort(OutputPort):
    def get_buf_type(self):
        return vm.Float()


class EventInputPort(InputPort):
    def __init__(self, *, csound_instr='1', **kwargs):
        super().__init__(**kwargs)
        self.csound_instr = csound_instr

    def check_port(self, port):
        super().check_port(port)
        if not isinstance(port, EventOutputPort):
            raise Error("Can only connect to EventOutputPort")

    def get_buf_type(self):
        return vm.AtomData()


class EventOutputPort(OutputPort):
    def get_buf_type(self):
        return vm.AtomData()
