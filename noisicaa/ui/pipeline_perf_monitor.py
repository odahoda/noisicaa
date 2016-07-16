#!/usr/bin/python

import os.path

from PyQt5 import QtGui
from PyQt5 import QtWidgets

from . import ui_base


class PipelinePerfMonitor(ui_base.CommonMixin, QtWidgets.QDialog):
    def __init__(self, app, parent):
        super().__init__(app=app, parent=parent)

        self.setWindowTitle("noisicaä - Pipeline Performance Monitor")
        self.resize(600, 300)

        self.bla = QtWidgets.QTextEdit(self)
        self.bla.setReadOnly(True)
        self.bla.setFont(QtGui.QFont('Courier New', 10))
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.bla)

        self.setLayout(layout)

        self.setVisible(
            int(self.app.settings.value(
                'dialog/pipeline_perf_monitor/visible', False)))
        self.restoreGeometry(
            self.app.settings.value(
                'dialog/pipeline_perf_monitor/geometry', b''))

    def storeState(self):
        s = self.app.settings
        s.beginGroup('dialog/pipeline_perf_monitor')
        s.setValue('visible', int(self.isVisible()))
        s.setValue('geometry', self.saveGeometry())
        s.endGroup()

    def addPerfData(self, perf_data):
        self.bla.setPlainText('\n'.join(str(s) for s in perf_data))
