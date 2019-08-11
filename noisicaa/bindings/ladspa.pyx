# @begin:license
#
# Copyright (c) 2015-2019, Benjamin Niemann <pink@odahoda.de>
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

from libc.stdint cimport uint8_t

from enum import Enum
import itertools
import math
import sys

import numpy
cimport numpy


class Error(Exception):
    pass


class PortDirection(Enum):
    Input = 'input'
    Output = 'output'


class PortType(Enum):
    Control = 'control'
    Audio = 'audio'


cdef class Port(object):
    def __str__(self):
        s = '<port "%s" %s %s' % (self.name, self.type.value, self.direction.value)
        if self.is_bounded:
            lower = self.lower_bound(1)
            upper = self.upper_bound(1)
            s += ' ['
            if lower is not None:
                s += str(lower)
            s += ':'
            if upper is not None:
                s += str(upper)
            s += ']'
            if self.is_sample_rate:
                s += '*sr'

        default = self.default(1)
        if default is not None:
            s += ' default=%f' % default

        if self.is_logarithmic:
            s += ' logarithmic'
        s += '>'
        return s

    @property
    def index(self):
        return self._index

    @property
    def name(self):
        return bytes(self._name).decode('ascii')

    @property
    def direction(self):
        if LADSPA_IS_PORT_INPUT(self._desc):
            return PortDirection.Input
        if LADSPA_IS_PORT_OUTPUT(self._desc):
            return PortDirection.Output

    @property
    def type(self):
        if LADSPA_IS_PORT_AUDIO(self._desc):
            return PortType.Audio
        if LADSPA_IS_PORT_CONTROL(self._desc):
            return PortType.Control

    @property
    def is_bounded(self):
        return bool(
            LADSPA_IS_HINT_BOUNDED_BELOW(self._range_hint.HintDescriptor)
            or LADSPA_IS_HINT_BOUNDED_ABOVE(self._range_hint.HintDescriptor))

    def lower_bound(self, sample_rate):
        if LADSPA_IS_HINT_BOUNDED_BELOW(self._range_hint.HintDescriptor):
            if self.is_integer:
                return int(self._range_hint.LowerBound)
            elif self.is_sample_rate:
                return self._range_hint.LowerBound * sample_rate
            else:
                return self._range_hint.LowerBound
        else:
            return None

    def upper_bound(self, sample_rate):
        if LADSPA_IS_HINT_BOUNDED_ABOVE(self._range_hint.HintDescriptor):
            if self.is_integer:
                return int(self._range_hint.UpperBound)
            elif self.is_sample_rate:
                return self._range_hint.UpperBound * sample_rate
            else:
                return self._range_hint.UpperBound
        else:
            return None

    def default(self, sample_rate):
        if LADSPA_IS_HINT_DEFAULT_0(self._range_hint.HintDescriptor):
            return 0.0
        if LADSPA_IS_HINT_DEFAULT_1(self._range_hint.HintDescriptor):
            return 1.0
        if LADSPA_IS_HINT_DEFAULT_100(self._range_hint.HintDescriptor):
            return 100.0
        if LADSPA_IS_HINT_DEFAULT_440(self._range_hint.HintDescriptor):
            return 440.0
        if LADSPA_IS_HINT_DEFAULT_MINIMUM(self._range_hint.HintDescriptor):
            return self.lower_bound(sample_rate)
        if LADSPA_IS_HINT_DEFAULT_MAXIMUM(self._range_hint.HintDescriptor):
            return self.upper_bound(sample_rate)
        if LADSPA_IS_HINT_DEFAULT_LOW(self._range_hint.HintDescriptor):
            return self.weighted_mean(sample_rate, 0.75, 0.25)
        if LADSPA_IS_HINT_DEFAULT_MIDDLE(self._range_hint.HintDescriptor):
            return self.weighted_mean(sample_rate, 0.5, 0.5)
        if LADSPA_IS_HINT_DEFAULT_HIGH(self._range_hint.HintDescriptor):
            return self.weighted_mean(sample_rate, 0.25, 0.75)

        return None

    def weighted_mean(self, sample_rate, w1, w2):
        lower = self.lower_bound(sample_rate)
        if lower is None:
            lower = 0.0
        upper = self.upper_bound(sample_rate)
        if upper is None:
            upper = lower + 1.0
        if self.is_logarithmic:
            try:
                return math.exp(w1 * math.log(lower) + w2 * math.log(upper))
            except ValueError:
                # Crappy plugins might specify a logarithmic port with
                # a lower bound of zero...
                return lower
        else:
            return w1 * lower + w2 * upper

    @property
    def is_sample_rate(self):
        return bool(LADSPA_IS_HINT_SAMPLE_RATE(self._range_hint.HintDescriptor))

    @property
    def is_logarithmic(self):
        return bool(LADSPA_IS_HINT_LOGARITHMIC(self._range_hint.HintDescriptor))

    @property
    def is_integer(self):
        return bool(LADSPA_IS_HINT_INTEGER(self._range_hint.HintDescriptor))


cdef class Instance(object):
    def __dealloc__(self):
        if self._handle != NULL:
            self._desc._desc.cleanup(self._handle)
            self._handle = NULL

    cdef connect_port(self, Port port, char* data):
        assert self._handle != NULL
        self._desc._desc.connect_port(self._handle, port.index, <LADSPA_Data*>data)

    cdef activate(self):
        assert self._handle != NULL
        if self._desc._desc.activate != NULL:
            self._desc._desc.activate(self._handle)

    cdef run(self, int num_samples):
        assert self._handle != NULL
        self._desc._desc.run(self._handle, num_samples)

    cdef deactivate(self):
        assert self._handle != NULL
        if self._desc._desc.deactivate != NULL:
            self._desc._desc.deactivate(self._handle)

    cdef cleanup(self):
        if self._handle != NULL:
            self._desc._desc.cleanup(self._handle)
            self._handle = NULL

    cdef close(self):
        self.cleanup()
        self._desc._instances.remove(self)


cdef class Descriptor(object):
    def __init__(self):
        self._instances = []
        self.ports = []

    def __dealloc__(self):
        self.close_all_instances()

    @property
    def id(self):
        return self._desc.UniqueID

    @property
    def label(self):
        return bytes(self._desc.Label).decode('ascii')

    @property
    def name(self):
        return bytes(self._desc.Name).decode('ascii')

    @property
    def maker(self):
        return bytes(self._desc.Maker).decode('ascii')

    @property
    def copyright(self):
        return bytes(self._desc.Copyright).decode('ascii')

    def instantiate(self, unsigned long sample_rate):
        cdef LADSPA_Handle handle

        handle = self._desc.instantiate(self._desc, sample_rate)
        if handle == NULL:
            raise Error
        instance = Instance()
        instance._desc = self
        instance._handle = handle
        self._instances.append(instance)
        return instance

    def close_all_instances(self):
        cdef Instance instance
        for instance in self._instances:
            instance.cleanup()
        self._instances.clear()


cdef class Library(object):
    def __init__(self, path):
        cdef char* error
        cdef LADSPA_Descriptor_Function ladspa_descriptor
        cdef const LADSPA_Descriptor* ld
        cdef object ld_object

        self.descriptors = []

        self.handle = dlopen(path.encode(sys.getfilesystemencoding()), RTLD_NOW)
        if self.handle == NULL:
            raise Error(dlerror().decode('utf-8'))

        ladspa_descriptor = <LADSPA_Descriptor_Function>dlsym(self.handle, "ladspa_descriptor")
        error = dlerror()
        if error != NULL:
            raise Error(unicode(error, 'utf-8'))

        for index in itertools.count(0):
            ld = ladspa_descriptor(index)
            if ld == NULL:
                break

            pd = Descriptor()
            pd._desc = ld
            for pindex in range(ld.PortCount):
                port = Port()
                port._index = pindex
                port._desc = ld.PortDescriptors[pindex]
                port._range_hint = ld.PortRangeHints[pindex]
                port._name = ld.PortNames[pindex]
                pd.ports.append(port)

            self.descriptors.append(pd)

    def __dealloc__(self):
        for descriptor in self.descriptors:
            descriptor.close_all_instances()
        self.descriptors.clear()

        if self.handle != NULL:
            dlclose(self.handle)
            self.handle = NULL

    def get_descriptor(self, label):
        for descriptor in self.descriptors:
            if descriptor.label == label:
                return descriptor
        raise KeyError(label)
