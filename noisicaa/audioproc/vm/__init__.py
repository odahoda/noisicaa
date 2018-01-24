# @begin:license
#
# Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
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

# TODO: pylint has issues with cython modules.
from .engine import PipelineVM  # pylint: disable=import-error
from .compiler import compile_graph
from .audio_stream import (  # pylint: disable=import-error
    AudioStream,
)
# pylint doesn't know about capnp import magic
import capnp  # pylint: disable=unused-import,wrong-import-order
from .block_data_capnp import (  # pylint: disable=import-error
    BlockData,
    Buffer,
)
from .spec import (  # pylint: disable=import-error
    PySpec as Spec
)
from .buffers import (  # pylint: disable=import-error
    PyBufferType as BufferType,
    PyFloat as Float,
    PyFloatAudioBlock as FloatAudioBlock,
    PyAtomData as AtomData,
)
from .control_value import (  # pylint: disable=import-error
    PyControlValueType as ControlValueType,
    PyFloatControlValue as FloatControlValue,
    PyIntControlValue as IntControlValue,
)
from .host_data import (  # pylint: disable=import-error
    PyHostData as HostData,
)
from .block_context import (  # pylint: disable=import-error
    PyBlockContext as BlockContext,
)
from .processor import (  # pylint: disable=import-error
    PyProcessor as Processor,
)
from .processor_spec import (  # pylint: disable=import-error
    PyProcessorSpec as ProcessorSpec,
)
