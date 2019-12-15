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

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets


class LineNumberArea(QtWidgets.QWidget):
    def __init__(self, editor: 'CodeEditor') -> None:
        super().__init__(editor)

        self.__code_editor = editor

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(self.__code_editor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        self.__code_editor.lineNumberAreaPaintEvent(event)


class CodeEditor(QtWidgets.QPlainTextEdit):
    def __init__(self, parent: QtWidgets.QWidget = None) -> None:
        super().__init__(parent)

        font = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont)
        font.setPointSizeF(self.font().pointSizeF())
        self.setFont(font)

        self.__line_number_area = LineNumberArea(self)

        self.blockCountChanged.connect(self.__updateLineNumberAreaWidth)
        self.updateRequest.connect(self.__updateLineNumberArea)
        self.cursorPositionChanged.connect(self.__highlightCurrentLine)

        self.__updateLineNumberAreaWidth(0)
        self.__highlightCurrentLine()

    def lineNumberAreaWidth(self) -> int:
        digits = 1
        max_num = max(1, self.blockCount())
        while max_num >= 10:
            max_num //= 10
            digits += 1

        space = 3 + self.fontMetrics().width('9') * digits
        return space

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        cr = self.contentsRect()
        width = self.lineNumberAreaWidth()
        rect = QtCore.QRect(cr.left(), cr.top(), width, cr.height())
        self.__line_number_area.setGeometry(rect)

    def lineNumberAreaPaintEvent(self, event: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self.__line_number_area)
        painter.fillRect(event.rect(), Qt.lightGray)
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        offset = self.contentOffset()
        top = int(self.blockBoundingGeometry(block).translated(offset).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(Qt.black)
                width = self.__line_number_area.width()
                height = self.fontMetrics().height()
                painter.drawText(0, top, width, height, Qt.AlignRight, number)

            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

    def __updateLineNumberAreaWidth(self, block_count: int) -> None:
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def __updateLineNumberArea(self, rect: QtCore.QRect, dy: int) -> None:
        if dy:
            self.__line_number_area.scroll(0, dy)
        else:
            width = self.__line_number_area.width()
            self.__line_number_area.update(0, rect.y(), width, rect.height())

        if rect.contains(self.viewport().rect()):
            self.__updateLineNumberAreaWidth(0)

    def __highlightCurrentLine(self) -> None:
        extra_selections = []

        if not self.isReadOnly():
            selection = QtWidgets.QTextEdit.ExtraSelection()

            line_color = QtGui.QColor(Qt.yellow).lighter(160)
            selection.format.setBackground(line_color)

            selection.format.setProperty(QtGui.QTextFormat.FullWidthSelection, True)

            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()

            extra_selections.append(selection)

        self.setExtraSelections(extra_selections)
