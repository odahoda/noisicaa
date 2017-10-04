#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2017, Benjamin Niemann <pink@odahoda.de>
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
import code
import sys
import textwrap
import traceback

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QTextOption, QTextCursor, QFont
from PyQt5.QtWidgets import QPlainTextEdit

logger = logging.getLogger('ui.command_shell')


class Interpreter(code.InteractiveInterpreter):
    def __init__(self, shell):
        self.locals = {
            '__name__': '__console__',
            '__doc__': None
        }

        super().__init__(self.locals)
        self.shell = shell

    def showsyntaxerror(self, filename=None):
        type, value, tb = sys.exc_info()  # pylint: disable=W0622
        sys.last_type = type
        sys.last_value = value
        sys.last_traceback = tb
        if filename and type is SyntaxError:
            # Work hard to stuff the correct filename in the exception
            try:
                msg, (dummy_filename, lineno, offset, line) = value.args
            except ValueError:
                # Not the format we expect; leave it alone
                pass
            else:
                # Stuff in the right filename
                value = SyntaxError(msg, (filename, lineno, offset, line))
                sys.last_value = value
        lines = traceback.format_exception_only(type, value)
        self.write(''.join(lines))

    def showtraceback(self):
        sys.last_type, sys.last_value, last_tb = ei = sys.exc_info()
        sys.last_traceback = last_tb
        try:
            lines = traceback.format_exception(ei[0], ei[1], last_tb.tb_next)
            self.write(''.join(lines))
        finally:
            last_tb = ei = None

    def write(self, data):
        self.shell.appendPlainText(data)


class CommandShell(QPlainTextEdit):
    PS1 = '>>> '
    PS2 = '... '
    MESSAGE = textwrap.dedent("""\
       Warning, this shell is only supposed to be used by experts for debugging.
       You're on your own now.
       """)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.history = []
        self.history_index = 0
        self.command = ''

        self.setGeometry(50, 75, 600, 400)
        self.setWordWrapMode(QTextOption.WrapAnywhere)
        self.setUndoRedoEnabled(False)
        self.document().setDefaultFont(QFont("monospace", 10, QFont.Normal))

        self.reset()

    def reset(self):
        self.interpreter = Interpreter(self)

        self.document().clear()
        self.appendPlainText(self.MESSAGE)
        self.command = ''
        self.newPrompt()

    def newPrompt(self):
        if not self.command:
            prompt = self.PS1
        else:
            prompt = self.PS2
        self.appendPlainText(prompt)
        self.moveCursor(QTextCursor.End)

    def getCommand(self):
        doc = self.document()
        curr_line = doc.findBlockByLineNumber(doc.lineCount() - 1).text()
        curr_line = curr_line[len(self.PS1):]
        return curr_line

    def setCommand(self, command):
        if self.getCommand() == command:
            return
        self.moveCursor(QTextCursor.End)
        self.moveCursor(QTextCursor.StartOfLine, QTextCursor.KeepAnchor)
        for _ in range(len(self.PS1)):
            self.moveCursor(QTextCursor.Right, QTextCursor.KeepAnchor)
        self.textCursor().removeSelectedText()
        self.textCursor().insertText(command)
        self.moveCursor(QTextCursor.End)

    def getHistory(self):
        return self.history

    def setHisory(self, history):
        self.history = history

    def addToHistory(self, command):
        if command and (not self.history or self.history[-1] != command):
            self.history.append(command)
        self.history_index = len(self.history)

    def getPrevHistoryEntry(self):
        if self.history:
            self.history_index = max(0, self.history_index - 1)
            return self.history[self.history_index]
        return ''

    def getNextHistoryEntry(self):
        if self.history:
            hist_len = len(self.history)
            self.history_index = min(hist_len, self.history_index + 1)
            if self.history_index < hist_len:
                return self.history[self.history_index]
        return ''

    def getCursorPosition(self):
        return self.textCursor().columnNumber() - len(self.PS1)

    def setCursorPosition(self, position):
        self.moveCursor(QTextCursor.StartOfLine)
        for _ in range(len(self.PS1) + position):
            self.moveCursor(QTextCursor.Right)

    def runCommand(self):
        command = self.getCommand()
        self.addToHistory(command)

        if self.command:
            self.command += '\n' + command
        else:
            self.command = command

        logger.info(repr(self.command))

        def displayhook(value):
            if value is not None:
                self.appendPlainText(repr(value))
        old_displayhook = sys.displayhook
        sys.displayhook = displayhook
        try:
            need_more = self.interpreter.runsource(self.command)
        finally:
            sys.displayhook = old_displayhook

        if not need_more:
            self.command = ''

        self.newPrompt()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Enter, Qt.Key_Return):
            self.runCommand()
            return
        if event.key() == Qt.Key_Home:
            self.setCursorPosition(0)
            return
        if event.key() == Qt.Key_PageUp:
            return
        elif event.key() in (Qt.Key_Left, Qt.Key_Backspace):
            if self.getCursorPosition() == 0:
                return
        elif event.key() == Qt.Key_Up:
            self.setCommand(self.getPrevHistoryEntry())
            return
        elif event.key() == Qt.Key_Down:
            self.setCommand(self.getNextHistoryEntry())
            return
        elif event.key() == Qt.Key_D and event.modifiers() == Qt.ControlModifier:
            self.reset()
        super().keyPressEvent(event)
