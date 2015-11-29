#!/usr/bin/python3

import logging

from PyQt5.QtWidgets import QGraphicsItem


logger = logging.getLogger(__name__)


class QGraphicsGroup(QGraphicsItem):
    def boundingRect(self):
        return self.childrenBoundingRect()

    def paint(self, painter, option, widget=None):
        pass
