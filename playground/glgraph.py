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


logger = logging.getLogger('glgraph')

logging.basicConfig(level=logging.INFO)


class NodeProgram(object):
    def __init__(self, gl):
        self.gl = gl

        vshader = QtGui.QOpenGLShader(QtGui.QOpenGLShader.Vertex)
        vshader.compileSourceCode(textwrap.dedent('''\
            attribute vec3 position;
            attribute vec4 tex_coord;
            varying vec4 texc;
            uniform mat4 matrix;

            void main(void)
            {
                gl_Position = matrix * vec4(position, 1.0);
                texc = tex_coord;
            }
            '''))

        fshader = QtGui.QOpenGLShader(QtGui.QOpenGLShader.Fragment)
        fshader.compileSourceCode(textwrap.dedent('''\
            uniform sampler2D texture;
            varying vec4 texc;

            void main(void)
            {
                gl_FragColor = texture2D(texture, texc.st);
            }
            '''))

        self.program = QtGui.QOpenGLShaderProgram()
        self.program.addShader(vshader)
        self.program.addShader(fshader)
        if not self.program.link():
            raise RuntimeError("Failed to link GL shader program: %s" % self.program.log())

        self.attrib_position = self.program.attributeLocation('position')
        self.attrib_tex_coord = self.program.attributeLocation('tex_coord')
        self.attrib_matrix = self.program.uniformLocation('matrix')


class NodeWidget(QtWidgets.QWidget):
    def __init__(self, name):
        super().__init__()

        self.name = name

        label = QtWidgets.QLabel(name)
        counter = QtWidgets.QLabel("0")
        edit = QtWidgets.QLineEdit()

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

class Node(QtCore.QObject):
    Render = QtCore.QEvent.registerEventType()

    def __init__(self, graph, name, pos, size):
        super().__init__()

        self.graph = graph
        self.name = name
        self.pos = pos
        self.size = size

        self.widget = None
        self.in_render = False
        self.fbo = None
        self.dirty_region = QtGui.QRegion()
        self.setWidget(NodeWidget(name))

    def setWidget(self, widget):
        if self.widget is not None:
            self._unmonitorObject(self.widget)
            self.widget.setParent(None)
            self.widget = None

        self.widget = widget

        if self.widget is not None:
            self._monitorObject(self.widget)
            self.widget.setParent(self.graph)
            self.widget.resize(self.size)

    def _monitorObject(self, obj):
        obj.installEventFilter(self)
        for child in obj.children():
           self._monitorObject(child)

    def _unmonitorObject(self, obj):
        for child in obj.children():
           self._unmonitorObject(child)
        self.removeEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.ChildAdded:
            logger.debug("%s: ChildAdded(%s)", obj, event.child())
            self._monitorObject(event.child())
        elif event.type() == QtCore.QEvent.ChildRemoved:
            logger.debug("%s: ChildRemoved(%s)", obj, event.child())
            self._unmonitorObject(event.child())
        elif event.type() == QtCore.QEvent.Paint:
            logger.debug("%s: Paint(%s)", obj, event.rect())
            if not self.in_render:
                region = event.region()
                region.translate(obj.mapTo(self.widget, QtCore.QPoint(0, 0)))
                self.dirty_region |= region
                QtCore.QCoreApplication.postEvent(self, QtCore.QEvent(self.Render))
                return True
        else:
            logger.debug(
                "%s: %s",
                obj,
                event_names.get(event.type(), '%s(%d)' % (type(event).__name__, event.type())))

        return super().eventFilter(obj, event)

    def event(self, event):
        if event.type() == self.Render:
            if not self.dirty_region.isEmpty():
                self.renderWidget(self.dirty_region)
                self.dirty_region = QtGui.QRegion()
            return True
        else:
            return super().event(event)

    def renderWidget(self, region=None):
        if self.widget is None:
            return

        if region is not None:
            rect = region.boundingRect()
        else:
            rect = QtCore.QRect(0, 0, self.size.width(), self.size.height())

        logger.debug("Start render of %s (%s)", self.name, rect)

        self.graph.makeCurrent()
        try:
            if self.fbo is None:
                fmt = QtGui.QOpenGLFramebufferObjectFormat()
                fmt.setAttachment(QtGui.QOpenGLFramebufferObject.CombinedDepthStencil)
                fmt.setTextureTarget(self.graph.gl.GL_TEXTURE_2D)
                self.fbo = QtGui.QOpenGLFramebufferObject(self.size, fmt)

            if not self.fbo.bind():
                raise RuntimeError("Failed to bind FBO")
            try:
                paint_device = QtGui.QOpenGLPaintDevice(self.size)
                painter = QtGui.QPainter(paint_device)
                try:
                    self.widget.initPainter(painter)
                    painter.setRenderHint(QtGui.QPainter.Antialiasing)

                    self.in_render = True
                    try:
                        self.widget.render(painter, rect.topLeft(), QtGui.QRegion(rect))
                    finally:
                        self.in_render = False

                finally:
                    painter.end()
            finally:
                if not self.fbo.release():
                    raise RuntimeError("Failed to release FBO")

            logger.debug("Finished render of %s", self.widget)

        finally:
            self.graph.doneCurrent()

    def update(self):
        pass

    def initializeGL(self, gl):
        self.gl = gl

        w, h = self.size.width(), self.size.height()

        self.vertices = array.array(
            'f',
            [0, 0,
             w, 0,
             w, h,
             0, h])

        self.tex_coords = array.array(
            'f',
            [0.0,  0.0,
             1.0,  0.0,
             1.0,  1.0,
             0.0,  1.0])

        self.renderWidget()

    def paintGL(self, program, global_matrix):
        if self.fbo is not None:
            program.program.bind()

            matrix = QtGui.QMatrix4x4()
            matrix.translate(self.pos.x(), self.pos.y())
            matrix = global_matrix * matrix

            program.program.setUniformValue('matrix', matrix)

            self.gl.glVertexAttribPointer(
                program.attrib_position, 2, self.gl.GL_FLOAT, False, 0, self.vertices)
            self.gl.glEnableVertexAttribArray(program.attrib_position)

            self.gl.glVertexAttribPointer(
                program.attrib_tex_coord, 2, self.gl.GL_FLOAT, False, 0, self.tex_coords)
            self.gl.glEnableVertexAttribArray(program.attrib_tex_coord)

            program.program.setUniformValue('texture', self.gl.GL_TEXTURE0)
            self.gl.glActiveTexture(self.gl.GL_TEXTURE0);
            self.gl.glBindTexture(self.gl.GL_TEXTURE_2D, self.fbo.texture());

            self.gl.glDrawArrays(self.gl.GL_TRIANGLE_FAN, 0, 4)


class GLGraph(QtWidgets.QOpenGLWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setFocusPolicy(Qt.StrongFocus)

        self.offset = QtCore.QPointF()
        self.zoom = 1.0

        self.zoom_dir = 0
        self.zoom_point = None
        self.zoom_steps = 0

        self.matrix = QtGui.QMatrix4x4()
        self.inv_matrix = QtGui.QMatrix4x4()

        self.last_pos = None

        self.gl = None

        self.updates = []
        self.update_timer = QtCore.QTimer(self)
        self.update_timer.setTimerType(Qt.PreciseTimer)
        self.update_timer.setInterval(1000.0 / 50)
        self.update_timer.timeout.connect(self.updateScene)

        self.nodes = []
        node = Node(
            graph=self,
            name='Master',
            pos=QtCore.QPointF(-200, -150),
            size=QtCore.QSize(400, 300),
        )
        self.nodes.append(node)

        for i in range(2):
            node = Node(
                graph=self,
                name='Node %d' % i,
                pos=QtCore.QPointF(random.uniform(-1000, 1000), random.uniform(-1000, 1000)),
                size=QtCore.QSize(random.uniform(100, 300), random.uniform(100, 200)),
            )
            self.nodes.append(node)

    def minimumSizeHint(self):
        return QtCore.QSize(50, 50)

    def sizeHint(self):
        return QtCore.QSize(400, 400)

    def initializeGL(self):
        ctxt = self.context()

        version = QtGui.QOpenGLVersionProfile()
        version.setVersion(4, 1)
        version.setProfile(QtGui.QSurfaceFormat.CoreProfile)
        self.gl = ctxt.versionFunctions(version)
        assert self.gl is not None
        self.gl.initializeOpenGLFunctions()

        logger.info("OpenGL Vendor: %s", self.gl.glGetString(self.gl.GL_VENDOR))
        logger.info("OpenGL Renderer: %s", self.gl.glGetString(self.gl.GL_RENDERER))
        logger.info("OpenGL Version: %s", self.gl.glGetString(self.gl.GL_VERSION))
        logger.info("Shader Version: %s", self.gl.glGetString(self.gl.GL_SHADING_LANGUAGE_VERSION))

        self.gl.glClearColor(0.8, 0.8, 1.0, 1.0)

        #self.gl.glEnable(self.gl.GL_DEPTH_TEST)
        #self.gl.glEnable(self.gl.GL_CULL_FACE)

        self.program = NodeProgram(self.gl)

        for node in self.nodes:
            node.initializeGL(self.gl)

    def paintGL(self):
        painter = QtGui.QPainter(self)
        try:
            painter.beginNativePainting()
            try:
                self.gl.glViewport(0, 0, self.width(), self.height())
                self.gl.glClear(self.gl.GL_COLOR_BUFFER_BIT | self.gl.GL_DEPTH_BUFFER_BIT)

                matrix = QtGui.QMatrix4x4()
                matrix.ortho(0, self.width(), 0, self.height(), -1.0, 1.0)
                matrix *= self.matrix

                for node in self.nodes:
                    node.paintGL(self.program, matrix)
            finally:
                painter.endNativePainting()

            painter.setRenderHint(QtGui.QPainter.TextAntialiasing)
            painter.drawText(0, 20, 'offset: %d, %d' % (self.offset.x(), self.offset.y()))

            self.updates.append(time.time())
            self.updates = self.updates[-10:]
            if len(self.updates) >= 5:
                dt = (self.updates[-1] - self.updates[0]) / len(self.updates)
                if dt > 0:
                    fps = 1.0 / dt
                    painter.drawText(0, 40, 'FPS: %.1f' % fps)

        finally:
            painter.end()

    def resizeGL(self, width, height):
        side = min(width, height)
        if side < 0:
            return

        self.updateMatrix()

    def updateMatrix(self):
        self.matrix = QtGui.QMatrix4x4()
        self.matrix.translate(self.offset.x() + self.width() / 2, self.offset.y() + self.height() / 2, 0)
        self.matrix.scale(self.zoom, self.zoom)
        self.inv_matrix, invertable = self.matrix.inverted()
        assert invertable

    def localToScene(self, local_pos):
        pos = QtCore.QPointF(local_pos.x(), self.height() - local_pos.y())
        pos = self.inv_matrix * pos
        return pos

    def sceneToLocal(self, scene_pos):
        pos = self.matrix * scene_pos
        pos = QtCore.QPointF(pos.x(), self.height() - pos.y())
        return pos

    def updateScene(self):
        if self.zoom_steps > 0:
            self.zoom_steps -= 1

            p_old = self.localToScene(self.zoom_point)
            self.zoom *= self.zoom_dir
            self.updateMatrix()

            p_new = self.sceneToLocal(p_old)
            delta = self.zoom_point - p_new
            self.offset += QtCore.QPointF(delta.x(), -delta.y())
            self.updateMatrix()

        for node in self.nodes:
            node.update()

        self.update()

    def showEvent(self, event):
        self.update_timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self.update_timer.stop()
        super().hideEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_R:
            self.zoom = 1.0
            self.offset = QtCore.QPointF(0, 0)
            self.updateMatrix()
            self.update()

    def mousePressEvent(self, event):
        print(self.localToScene(event.localPos()))
        if event.button() == Qt.MiddleButton:
            self.last_pos = event.pos()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self.last_pos = None

    def mouseMoveEvent(self, event):
        if self.last_pos is not None:
            delta = event.localPos() - self.last_pos
            if event.modifiers() & Qt.ShiftModifier:
                delta *= 5
            self.offset += QtCore.QPointF(delta.x(), -delta.y())
            self.last_pos = event.localPos()
            self.updateMatrix()
            self.update()

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0:
            self.zoom_dir = 1.2
            self.zoom_steps = 4
        else:
            self.zoom_dir = 1 / 1.2
            self.zoom_steps = 4
        self.zoom_point = event.posF()


app = QtWidgets.QApplication(sys.argv)

win = QtWidgets.QMainWindow()
win.setWindowTitle("GL Graph")
win.resize(800, 600)

gl_graph = GLGraph()
win.setCentralWidget(gl_graph)

win.show()

sys.exit(app.exec_())
