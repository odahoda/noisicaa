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
from typing import cast, Any, Dict

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import music
from noisicaa.ui import ui_base
from noisicaa.ui import vumeter
from noisicaa.ui import control_value_connector
from noisicaa.ui import control_value_dial
from noisicaa.ui import gain_slider
from noisicaa.ui import dynamic_layout
from noisicaa.ui.graph import base_node

logger = logging.getLogger(__name__)


class MixerNodeWidget(ui_base.ProjectMixin, QtWidgets.QWidget):
    def __init__(self, node: music.BaseNode, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__node = node
        self.__node.control_value_map.init()

        label_font = QtGui.QFont()
        label_font.setPixelSize(12)

        self.__hp_cutoff_control = control_value_connector.ControlValueConnector(
            node=node,
            name='hp_cutoff',
            context=self.context)
        self.__hp_cutoff_dial = control_value_dial.ControlValueDial(self)
        self.__hp_cutoff_dial.setRange(10.0, 20000.0)
        self.__hp_cutoff_dial.setDefault(1.0)
        self.__hp_cutoff_dial.setLogScale(True)
        self.__hp_cutoff_dial.setDisplayFunc(
            lambda value: '%.0fHz' % value if value > 10.0 else 'off')
        self.__hp_cutoff_control.connect(
            self.__hp_cutoff_dial.valueChanged,
            self.__hp_cutoff_dial.setValue)

        self.__hp_cutoff_label = QtWidgets.QLabel("HP", self)
        self.__hp_cutoff_label.setFont(label_font)
        self.__hp_cutoff_label.setAlignment(Qt.AlignHCenter)

        self.__lp_cutoff_control = control_value_connector.ControlValueConnector(
            node=node,
            name='lp_cutoff',
            context=self.context)
        self.__lp_cutoff_dial = control_value_dial.ControlValueDial(self)
        self.__lp_cutoff_dial.setRange(10.0, 20000.0)
        self.__lp_cutoff_dial.setDefault(20000.0)
        self.__lp_cutoff_dial.setLogScale(True)
        self.__lp_cutoff_dial.setDisplayFunc(
            lambda value: '%.0fHz' % value if value < 20000. else 'off')
        self.__lp_cutoff_control.connect(
            self.__lp_cutoff_dial.valueChanged,
            self.__lp_cutoff_dial.setValue)

        self.__lp_cutoff_label = QtWidgets.QLabel("LP", self)
        self.__lp_cutoff_label.setFont(label_font)
        self.__lp_cutoff_label.setAlignment(Qt.AlignHCenter)

        self.__gain_control = control_value_connector.ControlValueConnector(
            node=node,
            name='gain',
            context=self.context)
        self.__gain_dial = control_value_dial.ControlValueDial(self)
        self.__gain_dial.setRange(-40.0, 20.0)
        self.__gain_dial.setDefault(0.0)
        self.__gain_dial.setDisplayFunc(lambda value: '%+.2fdB' % value)
        self.__gain_control.connect(
            self.__gain_dial.valueChanged, self.__gain_dial.setValue)

        self.__gain_slider = gain_slider.GainSlider(self)
        self.__gain_slider.setRange(-40.0, 20.0)
        self.__gain_slider.setDefault(0.0)
        self.__gain_slider.setDisplayFunc(lambda value: '%+.2fdB' % value)
        self.__gain_control.connect(
            self.__gain_slider.valueChanged, self.__gain_slider.setValue)

        self.__gain_label = QtWidgets.QLabel("Gain", self)
        self.__gain_label.setFont(label_font)
        self.__gain_label.setAlignment(Qt.AlignHCenter)

        self.__pan_control = control_value_connector.ControlValueConnector(
            node=node,
            name='pan',
            context=self.context)
        self.__pan_dial = control_value_dial.ControlValueDial(self)
        self.__pan_dial.setRange(-1.0, 1.0)
        self.__pan_dial.setDefault(0.0)
        self.__pan_dial.setDisplayFunc(lambda value: '%.2f' % value)
        self.__pan_control.connect(
            self.__pan_dial.valueChanged,
            self.__pan_dial.setValue)

        self.__pan_label = QtWidgets.QLabel("Pan", self)
        self.__pan_label.setFont(label_font)
        self.__pan_label.setAlignment(Qt.AlignHCenter)

        self.__vu_meter = vumeter.VUMeter(self)

        self.__portrms_urid = self.app.urid_mapper.map(
            'http://noisicaa.odahoda.de/lv2/core#portRMS')
        self.__meter_urid = self.app.urid_mapper.map(
            'http://noisicaa.odahoda.de/lv2/processor_mixer#meter')
        self.__int_urid = self.app.urid_mapper.map(
            'http://lv2plug.in/ns/ext/atom#Int')
        self.__float_urid = self.app.urid_mapper.map(
            'http://lv2plug.in/ns/ext/atom#Float')

        self.__node_msg_listener = self.audioproc_client.node_messages.add(
            '%016x' % self.__node.id, self.__nodeMessage)

        self.setMinimumSize(QtCore.QSize(10, 10))

        self.__current_orientation = None  # type: Qt.Orientation

    def cleanup(self) -> None:
        if self.__node_msg_listener is not None:
            self.__node_msg_listener.remove()
            self.__node_msg_listener = None

    def __nodeMessage(self, msg: Dict[str, Any]) -> None:
        meter = 'http://noisicaa.odahoda.de/lv2/processor_mixer#meter'
        if meter in msg:
            current_left, peak_left, current_right, peak_right = msg[meter]
            self.__vu_meter.setLeftValue(current_left)
            self.__vu_meter.setLeftPeak(peak_left)
            self.__vu_meter.setRightValue(current_right)
            self.__vu_meter.setRightPeak(peak_right)

    def resizeEvent(self, evt: QtGui.QResizeEvent) -> None:
        super().resizeEvent(evt)

        w, h = self.width(), self.height()

        if w > h:
            orientation = Qt.Horizontal

        else:
            orientation = Qt.Vertical

        if orientation == self.__current_orientation:
            return

        if self.layout() is not None:
            cast(dynamic_layout.DynamicLayout, self.layout()).clear()
            QtWidgets.QWidget().setLayout(self.layout())

        self.__gain_slider.setOrientation(orientation)
        self.__vu_meter.setOrientation(orientation)

        if orientation == Qt.Horizontal:
            layout = dynamic_layout.DynamicLayout(
                dynamic_layout.VBox(
                    dynamic_layout.HBox(
                        dynamic_layout.FirstMatch(
                            dynamic_layout.Widget(self.__gain_slider, priority=1),
                            dynamic_layout.VBox(
                                dynamic_layout.Widget(self.__gain_dial, priority=1),
                                dynamic_layout.Widget(self.__gain_label, priority=4),
                            ),
                            stretch=1,
                        ),
                        dynamic_layout.VBox(
                            dynamic_layout.Widget(self.__hp_cutoff_dial, priority=3),
                            dynamic_layout.Widget(self.__hp_cutoff_label, priority=4),
                        ),
                        dynamic_layout.VBox(
                            dynamic_layout.Widget(self.__lp_cutoff_dial, priority=3),
                            dynamic_layout.Widget(self.__lp_cutoff_label, priority=4),
                        ),
                        dynamic_layout.VBox(
                            dynamic_layout.Widget(self.__pan_dial, priority=2),
                            dynamic_layout.Widget(self.__pan_label, priority=4),
                        ),
                    ),
                    dynamic_layout.Widget(self.__vu_meter),
                    spacing=2,
                )
            )
            self.setLayout(layout)

        elif orientation == Qt.Vertical:
            layout = dynamic_layout.DynamicLayout(
                dynamic_layout.HBox(
                    dynamic_layout.VBox(
                        dynamic_layout.HBox(
                            dynamic_layout.VBox(
                                dynamic_layout.Widget(self.__hp_cutoff_dial, priority=3),
                                dynamic_layout.Widget(self.__hp_cutoff_label, priority=4),
                            ),
                            dynamic_layout.VBox(
                                dynamic_layout.Widget(self.__lp_cutoff_dial, priority=3),
                                dynamic_layout.Widget(self.__lp_cutoff_label, priority=4),
                            ),
                        ),
                        dynamic_layout.VBox(
                            dynamic_layout.Widget(self.__pan_dial, priority=2),
                            dynamic_layout.Widget(self.__pan_label, priority=4),
                        ),
                        dynamic_layout.FirstMatch(
                            dynamic_layout.Widget(self.__gain_slider, priority=1),
                            dynamic_layout.VBox(
                                dynamic_layout.Widget(self.__gain_dial, priority=1),
                                dynamic_layout.Widget(self.__gain_label, priority=4),
                            ),
                            stretch=1,
                        ),
                    ),
                    dynamic_layout.Widget(self.__vu_meter),
                    spacing=2,
                )
            )
            self.setLayout(layout)

        else:
            raise AssertionError(orientation)

        self.__current_orientation = orientation


class MixerNode(base_node.Node):
    def __init__(self, *, node: music.BaseNode, **kwargs: Any) -> None:
        self.__widget = None  # type: MixerNodeWidget

        super().__init__(node=node, **kwargs)

    def cleanup(self) -> None:
        if self.__widget is not None:
            self.__widget.cleanup()
            self.__widget = None
        super().cleanup()

    def createBodyWidget(self) -> QtWidgets.QWidget:
        assert self.__widget is None
        self.__widget = MixerNodeWidget(node=self.node(), context=self.context)
        return self.__widget
