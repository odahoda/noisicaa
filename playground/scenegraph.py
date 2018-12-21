#!/usr/bin/python3

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


logger = logging.getLogger('scenegraph')

logging.basicConfig(level=logging.INFO)


class NodeWidget(QtWidgets.QWidget):
    def __init__(self, name):
        super().__init__()

        self.name = name

        label = QtWidgets.QLabel(name)
        counter = QtWidgets.QLabel("0")
        edit = QtWidgets.QPushButton("bla")

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(label)
        layout.addWidget(counter)
        layout.addWidget(edit)
        self.setLayout(layout)

        self.count = 0
        def step():
            self.count += 1
            counter.setText(str(self.count))

        self.timer = QtCore.QTimer()
        self.timer.setInterval(random.randint(900, 1100))
        self.timer.timeout.connect(step)
        self.timer.start()

    def __str__(self):
        return 'NodeWidget(%r)' % self.name


event_names = {
    val: name
    for name, val in QtCore.QEvent.__dict__.items()
    if isinstance(val, int)
}


class NodeProps(QtCore.QObject):
    rectChanged = QtCore.pyqtSignal(QtCore.QRect)
    viewRectChanged = QtCore.pyqtSignal(QtCore.QRect)


class Node(QtWidgets.QGraphicsItem):
    __next_zvalue = 2.0

    def __init__(self, name, rect):
        super().__init__()

        self.setZValue(1.0)
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.LeftButton)

        self.props = NodeProps()

        self.__rect = rect
        self.__view_rect = rect
        self.__transform = QtGui.QTransform()

        self.__drag_pos = None

        self.__box = QtWidgets.QGraphicsPathItem(self)
        pen = QtGui.QPen()
        pen.setColor(Qt.black)
        pen.setWidth(2)
        self.__box.setPen(pen)
        self.__box.setBrush(QtGui.QColor(200, 200, 200))
        self.__box.setOpacity(0.7)

        self.__title = QtWidgets.QGraphicsSimpleTextItem(self)
        self.__title.setText(name)

        self.__body = NodeWidget(name)
        self.__body.setAutoFillBackground(False)
        self.__body.setAttribute(Qt.WA_NoSystemBackground, True)

        self.__body_proxy = QtWidgets.QGraphicsProxyWidget(self)
        self.__body_proxy.setWidget(self.__body)

    def rect(self):
        return self.__rect

    def setRect(self, rect):
        self.__rect = rect
        self.updateViewRect()
        self.props.rectChanged.emit(self.__rect)

    def updateViewRect(self):
        self.__view_rect = self.__transform.mapRect(self.__rect)
        self.__layout()
        self.props.viewRectChanged.emit(self.__view_rect)

    def viewRect(self):
        return self.__view_rect

    def setTransform(self, transform):
        self.__transform = transform
        self.updateViewRect()

    def boundingRect(self):
        return self.__box.boundingRect()

    def __layout(self):
        self.setPos(self.__view_rect.topLeft())

        path = QtGui.QPainterPath()
        path.addRoundedRect(0, 0, self.__view_rect.width(), self.__view_rect.height(), 5, 5)
        self.__box.setPath(path)

        if self.__view_rect.height() > 20:
            self.__title.setVisible(True)
            self.__title.setPos(8, 0)
        else:
            self.__title.setVisible(False)

        bsize = self.__body_proxy.minimumSize()
        if (self.__view_rect.height() > bsize.height() + 34
            and self.__view_rect.width() > bsize.width() + 8):
            self.__body_proxy.setVisible(True)
            self.__body_proxy.setPos(4, 30)
            self.__body_proxy.resize(self.__view_rect.width() - 8, self.__view_rect.height() - 34)

        else:
            self.__body_proxy.setVisible(False)

    def paint(self, painter, option, widget):
        pass

    def mousePressEvent(self, event):
        self.setZValue(Node.__next_zvalue)
        Node.__next_zvalue += 1

        if event.button() == Qt.LeftButton:
            if self.__body_proxy.isVisible():
                title_rect = QtCore.QRect(0, 0, self.__view_rect.width(), 20)
            else:
                title_rect = QtCore.QRect(0, 0, self.__view_rect.width(), self.__view_rect.height())

            if title_rect.contains(event.pos().toPoint()):
                self.__drag_pos = event.scenePos()
                return

        event.ignore()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.__drag_pos is not None:
            self.__drag_pos = None
            return

        event.ignore()
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if self.__drag_pos is not None:
            delta = event.scenePos() - self.__drag_pos
            self.setRect(self.__transform.inverted()[0].mapRect(
                self.__view_rect.translated(delta.toPoint())))
            self.__drag_pos = event.scenePos()
            return

        event.ignore()
        super().mouseMoveEvent(event)

    def hoverEnterEvent(self, event):
        self.__box.setOpacity(1.0)
        return super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.__box.setOpacity(0.7)
        return super().hoverLeaveEvent(event)


class Connection(QtWidgets.QGraphicsPathItem):
    def __init__(self, node1, side1, pos1, node2, side2, pos2):
        super().__init__()

        pen = QtGui.QPen()
        pen.setColor(Qt.black)
        pen.setWidth(2)
        self.setPen(pen)

        self.__node1 = node1
        self.__side1 = side1
        self.__pos1 = pos1
        self.__node2 = node2
        self.__side2 = side2
        self.__pos2 = pos2

        self.__node1.props.viewRectChanged.connect(lambda _: self.__layout())
        self.__node2.props.viewRectChanged.connect(lambda _: self.__layout())

        self.__layout()

    def node1(self):
        return self.__node1

    def node2(self):
        return self.__node2

    def __layout(self):
        r1 = self.__node1.viewRect()
        if self.__side1 == 'left':
            pos1 = r1.topLeft()
        else:
            pos1 = r1.topRight()
        pos1 += QtCore.QPoint(0, self.__pos1 * r1.height() / 100)

        r2 = self.__node2.viewRect()
        if self.__side2 == 'left':
            pos2 = r2.topLeft()
        else:
            pos2 = r2.topRight()
        pos2 += QtCore.QPoint(0, self.__pos2 * r2.height() / 100)

        cpos = QtCore.QPointF(min(100, abs(pos2.x() - pos1.x()) / 2), 0)

        path = QtGui.QPainterPath()
        path.moveTo(pos1)
        path.cubicTo(pos1 + cpos, pos2 - cpos, pos2)
        self.setPath(path)



class SceneGraph(QtWidgets.QGraphicsView):
    def __init__(self):
        super().__init__()

        self.setMouseTracking(True)
        self.setRenderHints(
            QtGui.QPainter.Antialiasing
            | QtGui.QPainter.SmoothPixmapTransform
            | QtGui.QPainter.HighQualityAntialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setResizeAnchor(QtWidgets.QGraphicsView.NoAnchor)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.NoAnchor)
        self.setSceneRect(-100000, -100000, 200000, 200000)
        #self.setAlignment(Qt.Align)

        self.__scene = QtWidgets.QGraphicsScene()
        self.setScene(self.__scene)

        self.__nodes = []
        self.__connections = []

        self.__offset = QtCore.QPointF()
        self.__zoom = 1.0
        self.__transform = QtGui.QTransform()
        self.__transform.translate(self.__offset.x(), self.__offset.y())
        self.__transform.scale(self.__zoom, self.__zoom)
        self.__inv_transform, _ = self.__transform.inverted()

        self.__map_transform = QtGui.QTransform()
        self.__scene_rect = QtCore.QRect()

        self.__mouse_pos = QtCore.QPoint()

        self.__should_show_map = True
        self.__map_opacity = 1.0

        self.__drag_map = False

        self.__drag_start_pos = None

        self.__zoom_dir = 0
        self.__zoom_point = None
        self.__zoom_steps = 0

        self.__update_timer = QtCore.QTimer(self)
        self.__update_timer.setTimerType(Qt.PreciseTimer)
        self.__update_timer.setInterval(1000.0 / 50)
        self.__update_timer.timeout.connect(self.updateScene)

        for i in range(20):
            n = Node(
                "Node %d" % i,
                QtCore.QRect(
                    random.randint(-2000, 2000), random.randint(-1000, 1000),
                    random.randint(100, 300), random.randint(100, 300)))
            self.addNode(n)

        snodes = sorted(self.__nodes, key=lambda n: n.rect().left())
        for i, n1 in enumerate(snodes[:-1]):
            for _ in range(2):
                n2 = random.choice(snodes[i+1:])

                self.addConnection(n1, 'right', 45, n2, 'left', 45)
                self.addConnection(n1, 'right', 55, n2, 'left', 55)

        self.sceneRectChanged()
        self.layoutScene()

    def addNode(self, node):
        self.__scene.addItem(node)
        self.__nodes.append(node)
        node.props.rectChanged.connect(lambda _: self.sceneRectChanged())

    def addConnection(self, n1, s1, p1, n2, s2, p2):
        connection = Connection(n1, s1, p1, n2, s2, p2)
        self.__scene.addItem(connection)
        self.__connections.append(connection)

    def updateScene(self):
        if self.__zoom_steps > 0:
            self.__zoom_steps -= 1

            p_center = self.__transform.map(self.__zoom_point)
            p_old = self.__zoom_point
            self.__zoom = max(0.05, min(self.__zoom * self.__zoom_dir, 5.0))
            self.updateTransform()

            p_new = self.__transform.map(self.__zoom_point)
            delta = p_center - p_new
            self.__offset += QtCore.QPointF(delta.x(), delta.y())
            self.updateTransform()

            self.layoutScene()

        if (self.__should_show_map
            or self.__drag_map
            or (self.__map_opacity > 0.0 and self.mapRect().contains(self.__mouse_pos))):
            if self.__map_opacity < 1.0:
                self.__map_opacity = min(self.__map_opacity + 0.1, 1.0)
                self.viewport().update(self.mapRect())

        else:
            if self.__map_opacity > 0.0:
                self.__map_opacity = max(self.__map_opacity - 0.03, 0.0)
                self.viewport().update(self.mapRect())

    def updateTransform(self):
        self.__transform = QtGui.QTransform()
        self.__transform.translate(self.__offset.x(), self.__offset.y())
        self.__transform.scale(self.__zoom, self.__zoom)
        self.__inv_transform, _ = self.__transform.inverted()

        v_rect = self.__inv_transform.mapRect(self.viewport().rect())
        self.__should_show_map = not v_rect.contains(self.__scene_rect)
        self.viewport().update(self.mapRect())

    def layoutScene(self):
        for node in self.__nodes:
            node.setTransform(self.__transform)

    def sceneRectChanged(self):
        self.__scene_rect = QtCore.QRect()
        for node in self.__nodes:
            self.__scene_rect |= node.rect()

        size = max(self.__scene_rect.width(), self.__scene_rect.height())
        if size < 1000:
            m = (1000 - size) / 2
            self.__scene_rect += QtCore.QMargins(m, m, m, m)

        v_rect = self.__inv_transform.mapRect(self.viewport().rect())
        self.__should_show_map = not v_rect.contains(self.__scene_rect)
        self.viewport().update(self.mapRect())

    def mapRect(self):
        return QtCore.QRect(10, self.height() - 160, 200, 150)

    def paintEvent(self, event):
        super().paintEvent(event)

        r = self.mapRect()
        if event.rect().intersects(r) and self.__map_opacity > 0:
            w, h = r.width(), r.height()
            x, y = r.left(), r.top()

            painter = QtGui.QPainter(self.viewport())
            try:
                painter.setClipRect(r)
                painter.setOpacity(self.__map_opacity)
                painter.translate(x, y)

                painter.fillRect(0, 0, w, 1, Qt.black)
                painter.fillRect(0, h - 1, w, 1, Qt.black)
                painter.fillRect(0, 0, 1, h, Qt.black)
                painter.fillRect(w - 1, 0, 1, h, Qt.black)
                painter.fillRect(1, 0 + 1, w - 2, h - 2, QtGui.QColor(255, 255, 255, 240))

                self.__map_transform = QtGui.QTransform()
                self.__map_transform.translate(2, 2)
                scale = min(
                    1.0, (w - 4) / self.__scene_rect.width(), (h - 4) / self.__scene_rect.height())
                self.__map_transform.scale(scale, scale)
                self.__map_transform.translate(-self.__scene_rect.left(), -self.__scene_rect.top())

                painter.setPen(QtGui.QColor(100, 100, 100, 100))
                for conn in self.__connections:
                    painter.drawLine(
                        self.__map_transform.mapRect(conn.node1().rect()).center(),
                        self.__map_transform.mapRect(conn.node2().rect()).center())

                for node in self.__nodes:
                    painter.fillRect(self.__map_transform.mapRect(node.rect()), Qt.black)

                v_rect = self.__map_transform.mapRect(
                    self.__inv_transform.mapRect(self.viewport().rect()))
                painter.fillRect(v_rect, QtGui.QColor(150, 150, 255, 200))

            finally:
                painter.end()

    def showEvent(self, event):
        self.__update_timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self.__update_timer.stop()
        super().hideEvent(event)

    def mousePressEvent(self, event):
        if self.__map_opacity > 0 and self.mapRect().contains(event.pos()):
            if not self.__map_transform:
                return

            if event.button() in (Qt.LeftButton, Qt.MiddleButton):
                p = self.__map_transform.inverted()[0].map(
                    event.pos() - self.mapRect().topLeft())
                p = QtGui.QTransform().scale(self.__zoom, self.__zoom).map(p)
                v = self.viewport().rect()
                p -= QtCore.QPointF(v.width() / 2, v.height() / 2)
                self.__offset = -p
                self.updateTransform()
                self.layoutScene()

                self.__drag_map = True
            return

        super().mousePressEvent(event)
        if event.isAccepted():
            return

        if event.button() == Qt.MiddleButton:
            self.__drag_start_pos = event.pos()
            event.accept()
            return

    def mouseReleaseEvent(self, event):
        if self.__drag_map:
            self.__drag_map = False
            return

        if event.button() == Qt.MiddleButton and self.__drag_start_pos is not None:
            self.__drag_start_pos = None
            return

        return super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        self.__mouse_pos = event.pos()

        if self.__drag_map:
            p = self.__map_transform.inverted()[0].map(
                event.pos() - self.mapRect().topLeft())
            p = QtGui.QTransform().scale(self.__zoom, self.__zoom).map(p)
            v = self.viewport().rect()
            p -= QtCore.QPointF(v.width() / 2, v.height() / 2)
            self.__offset = -p
            self.updateTransform()
            self.layoutScene()
            return

        if self.__drag_start_pos is not None:
            delta = event.pos() - self.__drag_start_pos
            self.__drag_start_pos = event.pos()
            self.__offset += delta
            self.updateTransform()
            self.layoutScene()
            return

        return super().mouseMoveEvent(event)

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0:
            self.__zoom_dir = 1.2
            self.__zoom_steps = 4
        else:
            self.__zoom_dir = 1 / 1.2
            self.__zoom_steps = 4

        if self.mapRect().contains(event.pos()) and self.__map_transform is not None:
            self.__zoom_point = self.__map_transform.inverted()[0].map(
                event.pos() - self.mapRect().topLeft())

        else:
            self.__zoom_point = self.__inv_transform.map(event.pos())


app = QtWidgets.QApplication(sys.argv)

win = QtWidgets.QMainWindow()
win.setWindowTitle("Scene Graph")
win.resize(800, 600)

graph = SceneGraph()
win.setCentralWidget(graph)

win.show()

sys.exit(app.exec_())
