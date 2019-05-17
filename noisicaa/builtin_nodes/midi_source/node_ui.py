#!/usr/bin/python3

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

import logging
from typing import Any

from PyQt5.QtCore import Qt
from PyQt5 import QtWidgets

from noisicaa import core
from noisicaa import value_types
from noisicaa import music
from noisicaa.ui import device_list
from noisicaa.ui import dynamic_layout
from noisicaa.ui import piano
from noisicaa.ui import ui_base
from noisicaa.ui import property_connector
from noisicaa.ui.graph import base_node
from . import model
from . import processor_messages

logger = logging.getLogger(__name__)


class MidiSourceNodeWidget(ui_base.ProjectMixin, core.AutoCleanupMixin, QtWidgets.QWidget):
    def __init__(self, node: model.MidiSource, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__node = node

        form = QtWidgets.QWidget(self)
        form.setAutoFillBackground(False)
        form.setAttribute(Qt.WA_NoSystemBackground, True)

        self.__device_uri = device_list.PortSelector(self.app.devices, form)
        self.__device_uri_connector = property_connector.PortSelectorConnector(
            self.__device_uri, self.__node, 'device_uri',
            mutation_name='%s: Change device' % self.__node.name,
            context=self.context)
        self.add_cleanup_function(self.__device_uri_connector.cleanup)

        self.__channel_filter = QtWidgets.QComboBox(form)
        for value, text in [
                (-1, "All channels")] + [(value, "%d" % (value + 1)) for value in range(0, 16)]:
            self.__channel_filter.addItem(text, value)
        self.__channel_filter_connector = property_connector.QComboBoxConnector[int](
            self.__channel_filter, self.__node, 'channel_filter',
            mutation_name='%s: Change MIDI channel filter' % self.__node.name,
            context=self.context)
        self.add_cleanup_function(self.__channel_filter_connector.cleanup)

        form_layout = QtWidgets.QFormLayout()
        form_layout.setVerticalSpacing(1)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.addRow("Device:", self.__device_uri)
        form_layout.addRow("Channel filter:", self.__channel_filter)
        form.setLayout(form_layout)

        self.__piano = piano.PianoWidget(self)
        self.__piano.noteOn.connect(self.__noteOn)
        self.__piano.noteOff.connect(self.__noteOff)

        layout = dynamic_layout.DynamicLayout(
            dynamic_layout.VBox(
                dynamic_layout.Widget(form, priority=0),
                dynamic_layout.Widget(self.__piano, priority=1),
                spacing=2,
            )
        )
        self.setLayout(layout)

    def __noteOn(self, pitch: value_types.Pitch) -> None:
        if self.__node.channel_filter >= 0:
            channel = self.__node.channel_filter
        else:
            channel = 0

        self.call_async(self.project_view.sendNodeMessage(
            processor_messages.note_on_event(
                self.__node.pipeline_node_id, channel, pitch.midi_note, 100)))

    def __noteOff(self, pitch: value_types.Pitch) -> None:
        if self.__node.channel_filter >= 0:
            channel = self.__node.channel_filter
        else:
            channel = 0

        self.call_async(self.project_view.sendNodeMessage(
            processor_messages.note_off_event(
                self.__node.pipeline_node_id, channel, pitch.midi_note)))


class MidiSourceNode(base_node.Node):
    def __init__(self, *, node: music.BaseNode, **kwargs: Any) -> None:
        assert isinstance(node, model.MidiSource), type(node).__name__
        self.__widget = None  # type: MidiSourceNodeWidget
        self.__node = node  # type: model.MidiSource

        super().__init__(node=node, **kwargs)

    def createBodyWidget(self) -> QtWidgets.QWidget:
        assert self.__widget is None
        self.__widget = MidiSourceNodeWidget(node=self.__node, context=self.context)
        self.add_cleanup_function(self.__widget.cleanup)
        return self.__widget
