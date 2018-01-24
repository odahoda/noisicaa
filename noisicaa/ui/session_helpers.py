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
