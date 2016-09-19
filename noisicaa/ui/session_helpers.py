#!/usr/bin/python3

import functools
import logging
import math

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

logger = logging.getLogger(__name__)


class ManagedWindowMixin(object):
    def __init__(self, session_prefix, **kwargs):
        self.__init_done = False
        self.__session_prefix = session_prefix

        super().__init__(**kwargs)

        self.setVisible(self.get_session_value('visible', False))

        x, y = self.get_session_value('x', None), self.get_session_value('y', None)
        if x is not None and y is not None:
            self.move(x, y)

        w, h = self.get_session_value('w', None), self.get_session_value('h', None)
        if w is not None and h is not None:
            self.resize(w, h)

        self.__init_done = True

    def get_session_value(self, key, default):
        return super().get_session_value(self.__session_prefix + key, default)

    def set_session_value(self, key, value):
        super().set_session_value(self.__session_prefix + key, value)

    def set_session_values(self, data):
        super().set_session_values({
            self.__session_prefix + key: value
            for key, value in data.items()})

    def showEvent(self, evt):
        if self.__init_done:
            self.set_session_value('visible', True)
        super().showEvent(evt)

    def hideEvent(self, evt):
        if self.__init_done:
            self.set_session_value('visible', False)
        super().hideEvent(evt)

    def moveEvent(self, evt):
        if self.__init_done and self.isVisible():
            self.set_session_values({'x': evt.pos().x(), 'y': evt.pos().y()})
        super().moveEvent(evt)

    def resizeEvent(self, evt):
        if self.__init_done and self.isVisible():
            self.set_session_values({'w': evt.size().width(), 'h': evt.size().height()})
        super().resizeEvent(evt)

