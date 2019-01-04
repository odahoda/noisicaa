#!/usr/bin/python3

import functools
import array
import logging
import math
import sys
import textwrap
import time
import random

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa.ui import dynamic_layout

logger = logging.getLogger('dynamic_layout')

logging.basicConfig(level=logging.INFO)


class Wid(QtWidgets.QWidget):
    def __init__(self, *, color=QtGui.QColor(255, 255, 255), minimumSize=None, maximumSize=None, name, **kwargs):
        super().__init__(**kwargs)

        if minimumSize is not None:
            self.setMinimumSize(minimumSize)

        if maximumSize is not None:
            self.setMaximumSize(maximumSize)

        self.__color = color
        self.__name = name

    def __str__(self):
        return self.__name

    def paintEvent(self, evt: QtGui.QPaintEvent) -> None:
        w, h = self.width(), self.height()

        painter = QtGui.QPainter(self)
        try:
            painter.setRenderHints(
                QtGui.QPainter.Antialiasing | QtGui.QPainter.TextAntialiasing)

            painter.fillRect(0, 0, w, h, self.__color)

            font = QtGui.QFont("Arial")
            font.setPixelSize(14)
            painter.setFont(font)
            pen = QtGui.QPen()
            pen.setColor(Qt.black)
            painter.setPen(pen)
            painter.drawText(
                QtCore.QRect(0, 0, w, h),
                Qt.AlignCenter,
                '%s\n%s' % (self.__name, self.geometry()))

        finally:
            painter.end()


class Foo(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        layout = dynamic_layout.DynamicLayout(
            dynamic_layout.VBox(
                dynamic_layout.Widget(
                    Wid(parent=self,
                        name="p0",
                        color=QtGui.QColor(255, 200, 200),
                        minimumSize=QtCore.QSize(100, 40)),
                    priority=0,
                    stretch=1),
                dynamic_layout.HBox(
                    dynamic_layout.Widget(
                        Wid(parent=self,
                            name="p1",
                            color=QtGui.QColor(255, 255, 200),
                            minimumSize=QtCore.QSize(100, 40)),
                        priority=1,
                        stretch=1),
                    dynamic_layout.FirstMatch(
                        dynamic_layout.Widget(
                            Wid(parent=self,
                                name="p4+",
                                color=QtGui.QColor(100, 255, 100),
                                minimumSize=QtCore.QSize(200, 40)),
                            priority=4),
                        dynamic_layout.Widget(
                            Wid(parent=self,
                                name="p4",
                                color=QtGui.QColor(200, 255, 200),
                                minimumSize=QtCore.QSize(40, 40)),
                            priority=4),
                        stretch=2),
                    dynamic_layout.Widget(
                        Wid(parent=self,
                            name="p1",
                            color=QtGui.QColor(255, 255, 200),
                            minimumSize=QtCore.QSize(100, 40)),
                        priority=1,
                        stretch=1),
                ),
                dynamic_layout.Widget(
                    Wid(parent=self,
                        name="p2",
                        color=QtGui.QColor(255, 200, 255),
                        minimumSize=QtCore.QSize(100, 80)),
                    priority=2,
                    stretch=2),
                dynamic_layout.Widget(
                    Wid(parent=self,
                        name="p0",
                        color=QtGui.QColor(255, 200, 200),
                        minimumSize=QtCore.QSize(100, 40)),
                    priority=0,
                    stretch=1),
                spacing=2,
            )
        )

        self.setLayout(layout)


app = QtWidgets.QApplication(sys.argv)

win = QtWidgets.QMainWindow()
win.setWindowTitle("Dynamic Layout")
win.resize(800, 600)

win.setCentralWidget(Foo())

win.show()

sys.exit(app.exec_())
