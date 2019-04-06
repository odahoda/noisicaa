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

from .engine_notification_pb2 import (
    NodeStateChange,
    EngineStateChange,
    EngineNotification,
)
from .musical_time import (
    PyMusicalDuration as MusicalDuration,
    PyMusicalTime as MusicalTime,
)
from .time_mapper import (
    PyTimeMapper as TimeMapper,
)
from .control_value_pb2 import (
    ControlValue,
)
from .player_state_pb2 import (
    PlayerState,
)
from .plugin_state_pb2 import (
    PluginState,
    PluginStateLV2,
    PluginStateLV2Property,
)
from .instrument_spec_pb2 import (
    InstrumentSpec,
    SampleInstrumentSpec,
    SF2InstrumentSpec,
)
from .processor_message_pb2 import (
    ProcessorMessage,
    ProcessorMessageList,
)
from .devices_pb2 import (
    DeviceDescription,
    DevicePortDescription,
)
from .project_properties_pb2 import (
    ProjectProperties,
)
from .backend_settings_pb2 import (
    BackendSettings,
)
from .host_parameters_pb2 import (
    HostParameters,
)
from .node_port_properties_pb2 import (
    NodePortProperties,
)
from .node_parameters_pb2 import (
    NodeParameters,
)
