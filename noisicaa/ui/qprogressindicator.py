#!/usr/bin/env python

# @custom_license
#
# Taken from https://github.com/mojocorp/QProgressIndicator with minor modifications
# (use PySide2 instead of PySide).
#
# Original license:
#   Author: Jared P. Sutton <jpsutton@gmail.com>
#   License: LGPL
#   Note: I've licensed this code as LGPL because it was a complete translation of the
#   code found here...
#     https://github.com/mojocorp/QProgressIndicator

# Ignore formatting of 3rd party code for now.
# pylint: skip-file

import sys
from PySide2.QtCore import Qt
from PySide2 import QtCore
from PySide2 import QtGui
from PySide2 import QtWidgets

class QProgressIndicator(QtWidgets.QWidget):
  m_angle = None
  m_timerId = None
  m_delay = None
  m_displayedWhenStopped = None
  m_color = None

  def __init__ (self, parent):
    # Call parent class constructor first
    super(QProgressIndicator, self).__init__(parent)

    # Initialize Qt Properties
    self.setProperties()

    # Intialize instance variables
    self.m_angle = 0
    self.m_timerId = -1
    self.m_delay = 40
    self.m_displayedWhenStopped = False
    self.m_color = Qt.black

    # Set size and focus policy
    self.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
    self.setFocusPolicy(Qt.NoFocus)

    # Show the widget
    self.show()

  def animationDelay (self):
    return self.delay

  def isAnimated (self):
    return (self.m_timerId != -1)

  def isDisplayedWhenStopped (self):
    return self.displayedWhenStopped

  def getColor (self):
    return self.color

  def sizeHint (self):
    return QtCore.QSize(20, 20)

  def startAnimation (self):
    self.m_angle = 0

    if self.m_timerId == -1:
      self.m_timerId = self.startTimer(self.m_delay)

  def stopAnimation (self):
    if self.m_timerId != -1:
      self.killTimer(self.m_timerId)

    self.m_timerId = -1
    self.update()

  def setAnimationDelay (self, delay):
    if self.m_timerId != -1:
      self.killTimer(self.m_timerId)

    self.m_delay = delay

    if self.m_timerId != -1:
      self.m_timerId = self.startTimer(self.m_delay)

  def setDisplayedWhenStopped (self, state):
    self.displayedWhenStopped = state
    self.update()

  def setColor (self, color):
    self.m_color = color
    self.update()

  def timerEvent (self, event):
    self.m_angle = (self.m_angle + 30) % 360
    self.update()

  def paintEvent (self, event):
    if (not self.m_displayedWhenStopped) and (not self.isAnimated()):
      return

    width = min(self.width(), self.height())

    painter = QtGui.QPainter(self)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)

    outerRadius = (width - 1) * 0.5
    innerRadius = (width - 1) * 0.5 * 0.38

    capsuleHeight = outerRadius - innerRadius
    capsuleWidth  = capsuleHeight *.23 if (width > 32) else capsuleHeight *.35
    capsuleRadius = capsuleWidth / 2

    for i in range(0, 12):
      color = QtGui.QColor(self.m_color)

      if self.isAnimated():
        color.setAlphaF(1.0 - (i / 12.0))
      else:
        color.setAlphaF(0.2)

      painter.setPen(Qt.NoPen)
      painter.setBrush(color)
      painter.save()
      painter.translate(self.rect().center())
      painter.rotate(self.m_angle - (i * 30.0))
      painter.drawRoundedRect(capsuleWidth * -0.5, (innerRadius + capsuleHeight) * -1, capsuleWidth, capsuleHeight, capsuleRadius, capsuleRadius)
      painter.restore()

  def setProperties (self):
    self.delay = QtCore.Property(int, self.animationDelay, self.setAnimationDelay)
    self.displayedWhenStopped = QtCore.Property(bool, self.isDisplayedWhenStopped, self.setDisplayedWhenStopped)
    self.color = QtCore.Property(QtGui.QColor, self.getColor, self.setColor)


def TestProgressIndicator ():
  app = QtWidgets.QApplication(sys.argv)
  progress = QProgressIndicator(None)
  progress.setAnimationDelay(70)
  progress.startAnimation()

  # Execute the application
  sys.exit(app.exec_())

if __name__ == "__main__":
  TestProgressIndicator()
