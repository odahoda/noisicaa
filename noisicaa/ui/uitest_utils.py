#!/usr/bin/python3

import argparse
import unittest
import inspect
import logging
import os.path

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QPainter, QColor

from noisicaa.runtime_settings import RuntimeSettings
from .editor_app import BaseEditorApp


class MockSettings(object):
    def __init__(self):
        self._data = {}

    def value(self, key, default):
        return self._data.get(key, default)

    def setValue(self, key, value):
        self._data[key] = value

    def allKeys(self):
        return list(self._data.keys())


class MockSequencer(object):
    def __init__(self):
        self._ports = []

    def add_port(self, port_info):
        self._ports.append(port_info)

    def list_all_ports(self):
        yield from self._ports

    def get_pollin_fds(self):
        return []

    def connect(self, port_info):
        pass

    def disconnect(self, port_info):
        pass

    def close(self):
        pass

    def get_event(self):
        return None


class MockApp(BaseEditorApp):
    def __init__(self):
        super().__init__(RuntimeSettings(), MockSettings())

    def createSequencer(self):
        return MockSequencer()


class UITest(unittest.TestCase):
    # There are random crashes if we create and destroy the QApplication for
    # each test. So create a single one and re-use it for all tests. This
    # makes the tests non-hermetic, which could be a problem, but it's better
    # than fighting with the garbage collection in pyqt5.
    app = None

    def setUp(self):
        if UITest.app is None:
            UITest.app = MockApp()
        UITest.app.setup()

    def tearDown(self):
        UITest.app.cleanup()

    _snapshot_numbers = {}

    def create_snapshot(self, obj, zoom=1.0, raster=False):
        case_name = self.__class__.__name__

        frames = inspect.getouterframes(inspect.currentframe())
        for frame in frames:
            if frame[3].startswith('test_'):
                test_name = frame[3]
                break
        else:
            raise RuntimeError("Can't find test name")

        num = self._snapshot_numbers.setdefault((case_name, test_name), 0)
        self._snapshot_numbers[(case_name, test_name)] += 1

        img_name = '%s.%s.%d.png' % (case_name, test_name, num)

        image = QImage(
            int(zoom * obj.width()) + 20,
            int(zoom * obj.height()) + 20,
            QImage.Format_ARGB32)
        painter = QPainter(image)

        painter.save()
        painter.fillRect(
            0, 0, int(zoom * obj.width()) + 20, int(zoom * obj.height()) + 20,
            QColor(255, 0, 0))
        painter.fillRect(
            10, 10, int(zoom * obj.width()), int(zoom * obj.height()),
            Qt.white)
        painter.restore()

        if raster:
            painter.save()
            painter.setPen(QColor(200, 200, 200))

            for x in range(10, int(zoom * obj.width()) + 10, 10):
                painter.drawLine(x, 10, x, int(zoom * obj.height()) + 9)
            for y in range(10, int(zoom * obj.height()) + 10, 10):
                painter.drawLine(10, y, int(zoom * obj.width()) + 9, y)
            painter.restore()

        painter.setViewport(10, 10, zoom * obj.width(), zoom * obj.height())
        obj.render(painter)
        painter.end()
        logging.info("Saving snapshot %s...", test_name)
        image.save(os.path.join('/tmp', img_name))
