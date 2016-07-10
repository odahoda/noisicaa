#!/usr/bin/python3

import logging
import os.path
import enum

from PyQt5.QtCore import Qt, QSize, pyqtSignal, QMargins
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QWidget,
    QToolButton,
    QButtonGroup,
    QLayout,
    QSizePolicy,
)

from .flowlayout import FlowLayout
from ..constants import DATA_DIR
from .dock_widget import DockWidget
from . import ui_base

logger = logging.getLogger(__name__)


class Tool(enum.IntEnum):
    # pylint: disable=bad-whitespace

    NOTE_WHOLE   = 100
    NOTE_HALF    = 101
    NOTE_QUARTER = 102
    NOTE_8TH     = 103
    NOTE_16TH    = 104
    NOTE_32TH    = 105

    REST_WHOLE   = 200
    REST_HALF    = 201
    REST_QUARTER = 202
    REST_8TH     = 203
    REST_16TH    = 204
    REST_32TH    = 205

    ACCIDENTAL_NATURAL      = 300
    ACCIDENTAL_FLAT         = 301
    ACCIDENTAL_SHARP        = 302
    ACCIDENTAL_DOUBLE_FLAT  = 303
    ACCIDENTAL_DOUBLE_SHARP = 304

    DURATION_DOT        = 400
    DURATION_TRIPLET    = 401
    DURATION_QUINTUPLET = 402

    @property
    def is_note(self):
        return Tool.NOTE_WHOLE <= self <= Tool.NOTE_32TH

    @property
    def is_rest(self):
        return Tool.REST_WHOLE <= self <= Tool.REST_32TH

    @property
    def is_accidental(self):
        return Tool.ACCIDENTAL_NATURAL <= self <= Tool.ACCIDENTAL_DOUBLE_SHARP

    @property
    def is_duration(self):
        return Tool.DURATION_DOT <= self <= Tool.DURATION_QUINTUPLET


class ToolsDockWidget(DockWidget):
    toolChanged = pyqtSignal(Tool)

    def __init__(self, app, parent):
        super().__init__(
            app=app,
            parent=parent,
            identifier='tools',
            title="Tools",
            allowed_areas=Qt.AllDockWidgetAreas,
            initial_area=Qt.RightDockWidgetArea,
            initial_visible=True)

        self.group = QButtonGroup()
        self.layout = FlowLayout(spacing=1)

        self.addButton(Tool.NOTE_WHOLE, 'note-whole.svg')
        self.addButton(Tool.NOTE_HALF, 'note-half.svg')
        self.addButton(Tool.NOTE_QUARTER, 'note-quarter.svg')
        self.addButton(Tool.NOTE_8TH, 'note-8th.svg')
        self.addButton(Tool.NOTE_16TH, 'note-16th.svg')
        self.addButton(Tool.NOTE_32TH, 'note-32th.svg')

        self.addButton(Tool.REST_WHOLE, 'rest-whole.svg')
        self.addButton(Tool.REST_HALF, 'rest-half.svg')
        self.addButton(Tool.REST_QUARTER, 'rest-quarter.svg')
        self.addButton(Tool.REST_8TH, 'rest-8th.svg')
        self.addButton(Tool.REST_16TH, 'rest-16th.svg')
        self.addButton(Tool.REST_32TH, 'rest-32th.svg')

        self.addButton(Tool.ACCIDENTAL_NATURAL, 'accidental-natural.svg')
        self.addButton(Tool.ACCIDENTAL_SHARP, 'accidental-sharp.svg')
        self.addButton(Tool.ACCIDENTAL_FLAT, 'accidental-flat.svg')
        # double accidentals are not properly supported yet.
        #self.addButton(Tool.ACCIDENTAL_DOUBLE_SHARP, 'accidental-double-sharp.svg')
        #self.addButton(Tool.ACCIDENTAL_DOUBLE_FLAT, 'accidental-double-flat.svg')

        self.addButton(Tool.DURATION_DOT, 'duration-dot.svg')
        self.addButton(Tool.DURATION_TRIPLET, 'duration-triplet.svg')
        self.addButton(Tool.DURATION_QUINTUPLET, 'duration-quintuplet.svg')

        current_tool = int(
            self.app.settings.value('tool/current', Tool.NOTE_QUARTER))
        for button in self.group.buttons():
            if self.group.id(button) == current_tool:
                button.setChecked(True)

        self.group.buttonClicked.connect(self.onButtonClicked)

        main_area = QWidget()
        main_area.setLayout(self.layout)
        main_area.setContentsMargins(QMargins(0, 0, 0, 0))
        self.setWidget(main_area)

    def addButton(self, tool_id, icon):
        button = QToolButton(
            icon=QIcon(os.path.join(DATA_DIR, 'icons', icon)),
            iconSize=QSize(32, 32),
            checkable=True,
            autoRaise=True)
        self.group.addButton(button, tool_id)
        self.layout.addWidget(button)

    def onButtonClicked(self, button):
        tool_id = self.group.id(button)
        self.app.settings.setValue('tool/current', tool_id)
        self.toolChanged.emit(Tool(tool_id))

    def currentTool(self):
        return Tool(self.group.checkedId())

    def setCurrentTool(self, tool):
        for button in self.group.buttons():
            if self.group.id(button) == tool:
                button.setChecked(True)
