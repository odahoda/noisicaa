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
import typing
from typing import Any

from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets

from noisicaa import core
from noisicaa import music
from . import ui_base
from . import slots

logger = logging.getLogger(__name__)

MIME_TYPE = 'application/x-noisicaa-clipboard-data'


class Clipboard(core.AutoCleanupMixin, ui_base.CommonMixin, QtCore.QObject):
    def __init__(self, *, qt_app: QtWidgets.QApplication, **kwargs: Any) -> None:
        super().__init__(parent=qt_app, **kwargs)

        self.__qt_app = qt_app
        self.__qclipboard = self.__qt_app.clipboard()

        self.__can_copy_conn = None  # type: QtCore.pyqtConnection
        self.__can_cut_conn = None  # type: QtCore.pyqtConnection

        self.__widget = None  # type: CopyableMixin
        self.__contents = None  # type: music.ClipboardContents

        self.cut_action = QtWidgets.QAction("Cut", self)
        self.cut_action.setShortcut(QtGui.QKeySequence.Cut)
        self.cut_action.triggered.connect(self.__onCut)

        self.copy_action = QtWidgets.QAction("Copy", self)
        self.copy_action.setShortcut(QtGui.QKeySequence.Copy)

        self.copy_action.triggered.connect(self.__onCopy)

        self.paste_as_link_action = QtWidgets.QAction("Paste as link", self)
        self.paste_as_link_action.setShortcut("ctrl+shift+v")
        self.paste_as_link_action.triggered.connect(self.__onPasteAsLink)

        self.paste_action = QtWidgets.QAction("Paste", self)
        self.paste_action.setShortcut(QtGui.QKeySequence.Paste)
        self.paste_action.triggered.connect(self.__onPaste)

    def setup(self) -> None:
        self.__qclipboardChanged()
        conn = self.__qclipboard.dataChanged.connect(self.__qclipboardChanged)
        self.add_cleanup_function(lambda conn=conn: self.__qclipboard.dataChanged.disconnect(conn))  # type: ignore

        self.__focusChanged(None, self.__qt_app.focusWidget())
        conn = self.__qt_app.focusChanged.connect(self.__focusChanged)
        self.add_cleanup_function(lambda conn=conn: self.__qt_app.focusChanged.disconnect(conn))  # type: ignore

    def store(self, data: music.ClipboardContents) -> None:
        mime_data = QtCore.QMimeData()
        mime_data.setData(MIME_TYPE, data.SerializeToString())
        self.__qclipboard.setMimeData(mime_data)

    def __focusChanged(self, old_widget: QtWidgets.QWidget, new_widget: QtWidgets.QWidget) -> None:
        if self.__widget is not None:
            self.__widget.canCopyChanged.disconnect(self.__can_copy_conn)
            self.__can_copy_conn = None
            self.__widget.canCutChanged.disconnect(self.__can_cut_conn)
            self.__can_cut_conn = None
            self.__widget = None

        if isinstance(new_widget, CopyableMixin):
            self.__widget = new_widget
            self.copy_action.setEnabled(self.__widget.canCopy())
            self.__can_copy_conn = self.__widget.canCopyChanged.connect(self.copy_action.setEnabled)
            self.cut_action.setEnabled(self.__widget.canCut())
            self.__can_cut_conn = self.__widget.canCutChanged.connect(self.cut_action.setEnabled)

        else:
            self.cut_action.setEnabled(False)
            self.copy_action.setEnabled(False)

        self.__updateActions()

    def __qclipboardChanged(self) -> None:
        self.__contents = None

        mime_data = self.__qclipboard.mimeData()
        if mime_data is None:
            return

        if not mime_data.hasFormat(MIME_TYPE):
            logger.info("unsupported clipboard contents (%s)", ", ".join(mime_data.formats()))
            return

        self.__contents = music.ClipboardContents()
        self.__contents.ParseFromString(mime_data.data(MIME_TYPE))

        logger.info("Clipboard contents changed:\n%s", self.__contents)

        self.__updateActions()

    def __updateActions(self) -> None:
        if self.__widget is not None and self.__contents is not None:
            self.paste_action.setEnabled(self.__widget.canPaste(self.__contents))
            self.paste_as_link_action.setEnabled(self.__widget.canPasteAsLink(self.__contents))

        else:
            self.paste_action.setEnabled(False)
            self.paste_as_link_action.setEnabled(False)

    def __onCut(self) -> None:
        if self.__widget is None:
            logger.error("oops, no widget")
            return

        data = self.__widget.cutToClipboard()
        if data is not None:
            self.store(data)

    def __onCopy(self) -> None:
        if self.__widget is None:
            logger.error("oops, no widget")
            return

        data = self.__widget.copyToClipboard()
        if data is not None:
            self.store(data)

    def __onPaste(self) -> None:
        if self.__contents is None:
            logger.error("oops, no contents")
            return
        if self.__widget is None:
            logger.error("oops, no widget")
            return
        if not self.__widget.canPaste(self.__contents):
            logger.error("oops, can't paste that")
            return

        self.__widget.pasteFromClipboard(self.__contents)

    def __onPasteAsLink(self) -> None:
        if self.__contents is None:
            logger.error("oops, no contents")
            return
        if self.__widget is None:
            logger.error("oops, no widget")
            return
        if not self.__widget.canPasteAsLink(self.__contents):
            logger.error("oops, can't paste that")
            return

        self.__widget.pasteAsLinkFromClipboard(self.__contents)


if typing.TYPE_CHECKING:
    QWidgetMixin = QtWidgets.QWidget
else:
    QWidgetMixin = object


class CopyableMixin(slots.SlotContainer, QWidgetMixin):
    canCut, setCanCut, canCutChanged = slots.slot(bool, 'canCut', default=False)
    canCopy, setCanCopy, canCopyChanged = slots.slot(bool, 'canCopy', default=False)

    def copyToClipboard(self) -> music.ClipboardContents:
        return None

    def cutToClipboard(self) -> music.ClipboardContents:
        return None

    def canPaste(self, data: music.ClipboardContents) -> bool:
        return False

    def pasteFromClipboard(self, data: music.ClipboardContents) -> None:
        pass

    def canPasteAsLink(self, data: music.ClipboardContents) -> bool:
        return False

    def pasteAsLinkFromClipboard(self, data: music.ClipboardContents) -> None:
        pass


class CopyableDelegatorMixin(CopyableMixin):
    delegatedCopyable, setDelegatedCopyable, delegatedCopyableChanged = slots.slot(
        CopyableMixin, 'delegatedCopyable')

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__can_copy_conn = None  # type: QtCore.pyqtConnection
        self.__can_cut_conn = None  # type: QtCore.pyqtConnection

        self.delegatedCopyableChanged.connect(self.__delegatedCopyableChanged)

    def __delegatedCopyableChanged(self, delegate: CopyableMixin) -> None:
        if self.__can_copy_conn is not None:
            self.canCopyChanged.disconnect(self.__can_copy_conn)
            self.__can_copy_conn = None

        if self.__can_cut_conn is not None:
            self.canCutChanged.disconnect(self.__can_cut_conn)
            self.__can_cut_conn = None

        if delegate is not None:
            self.setCanCopy(delegate.canCopy())
            self.__can_copy_conn = delegate.canCopyChanged.connect(self.setCanCopy)

            self.setCanCut(delegate.canCut())
            self.__can_cut_conn = delegate.canCutChanged.connect(self.setCanCut)

    def copyToClipboard(self) -> music.ClipboardContents:
        delegate = self.delegatedCopyable()
        if delegate is not None:
            return delegate.copyToClipboard()
        return None

    def cutToClipboard(self) -> music.ClipboardContents:
        delegate = self.delegatedCopyable()
        if delegate is not None:
            return delegate.cutToClipboard()
        return None

    def canPaste(self, data: music.ClipboardContents) -> bool:
        delegate = self.delegatedCopyable()
        if delegate is not None:
            return delegate.canPaste(data)
        return False

    def pasteFromClipboard(self, data: music.ClipboardContents) -> None:
        delegate = self.delegatedCopyable()
        if delegate is not None:
            delegate.pasteFromClipboard(data)

    def canPasteAsLink(self, data: music.ClipboardContents) -> bool:
        delegate = self.delegatedCopyable()
        if delegate is not None:
            return delegate.canPasteAsLink(data)
        return False

    def pasteAsLinkFromClipboard(self, data: music.ClipboardContents) -> None:
        delegate = self.delegatedCopyable()
        if delegate is not None:
            delegate.pasteAsLinkFromClipboard(data)
