#!/usr/bin/python3

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

import logging
from typing import Any, List  # pylint: disable=unused-import

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtWidgets

from noisicaa import core  # pylint: disable=unused-import
from noisicaa import music
from noisicaa import model
from . import dock_widget
from . import ui_base

logger = logging.getLogger(__name__)


class ProjectProperties(ui_base.ProjectMixin, QtWidgets.QWidget):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__listeners = []  # type: List[core.Listener]

        self.__bpm = QtWidgets.QSpinBox(self)
        self.__bpm.setRange(1, 1000)
        self.__bpm.valueChanged.connect(self.onBPMEdited)
        self.__bpm.setValue(self.project.bpm)
        self.__listeners.append(self.project.bpm_changed.add(self.onBPMChanged))

        self.__form_layout = QtWidgets.QFormLayout()
        self.__form_layout.setSpacing(1)
        self.__form_layout.setContentsMargins(QtCore.QMargins(0, 0, 0, 0))
        self.__form_layout.addRow("BPM", self.__bpm)

        self.setLayout(self.__form_layout)

    # TODO: this gets never called...
    def cleanup(self) -> None:
        for listener in self.__listeners:
            listener.remove()
        self.__listeners.clear()

    def onBPMChanged(self, change: model.PropertyValueChange[int]) -> None:
        self.__bpm.setValue(change.new_value)

    def onBPMEdited(self, bpm: int) -> None:
        if bpm != self.project.bpm:
            self.send_command_async(music.Command(
                target=self.project.id,
                update_project_properties=music.UpdateProjectProperties(bpm=bpm)))


class ProjectPropertiesDockWidget(ui_base.ProjectMixin, dock_widget.DockWidget):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            identifier='project-properties',
            title="Project Properties",
            allowed_areas=Qt.AllDockWidgetAreas,
            initial_area=Qt.RightDockWidgetArea,
            initial_visible=True,
            **kwargs)

        self.setWidget(ProjectProperties(context=self.context))
