#!/usr/bin/python3

import asyncio
import os
import gc
import traceback
import threading

import nanogui
from nanogui import nanovg


class Node(nanogui.Widget):
    def __init__(self, parent, title):
        super().__init__(parent)

        layout = nanogui.AdvancedGridLayout([0], [0, 0])
        layout.setMargin(4)
        layout.setColStretch(0, 1.0)
        layout.setRowStretch(1, 1.0)
        self.setLayout(layout)

        titlebar = nanogui.Label(self, title)
        titlebar.setColor(nanogui.Color(0.0, 0.0, 0.0, 1.0))
        layout.setAnchor(titlebar, nanogui.AdvancedGridLayout.Anchor(0, 0))

        body = nanogui.Widget(self)
        layout.setAnchor(body, nanogui.AdvancedGridLayout.Anchor(0, 1))

        nanogui.CheckBox(body, "A check box")

        self.__highlighted = False
        self.__drag_handle_pos = None

    def draw(self, ctx):
        if self.__highlighted:
            bg_color = nanogui.Color(0.95, 0.95, 0.95, 1.0)
            frame_color = nanogui.Color(0.0, 0.0, 0.0, 1.0)
        else:
            bg_color = nanogui.Color(0.95, 0.95, 0.95, 0.6)
            frame_color = nanogui.Color(0.0, 0.0, 0.0, 0.6)

        x, y = self.position()
        w, h = self.size()

        ctx.BeginPath()
        ctx.RoundedRect(x + 1, y + 1, w - 2, h - 2, 5)
        ctx.FillColor(bg_color)
        ctx.Fill()

        super().draw(ctx)

        ctx.BeginPath()
        ctx.RoundedRect(x + 1, y + 1, w - 2, h - 2, 5)
        ctx.StrokeWidth(2.0)
        ctx.StrokeColor(frame_color)
        ctx.Stroke()

    def mouseEnterEvent(self, pos, enter):
        if enter:
            self.__highlighted = True
            return True

        if not enter:
            self.__drag_handle_pos = None
            self.__highlighted = False
            return True

        #print("mouseEnterEvent(%s, %s)" % (pos, enter))
        return super().mouseEnterEvent(pos, enter)

    def mouseButtonEvent(self, pos, button, down, modifiers):
        if super().mouseButtonEvent(pos, button, down, modifiers):
            return True

        if button == 0 and down:
            self.__drag_handle_pos = pos
            return True

        if button == 0 and not down:
            self.__drag_handle_pos = None
            return True

        #print("mouseButtonEvent(%s, %s, %s, %s)" % (pos, button, down, modifiers))
        return False

    def mouseMotionEvent(self, pos, rel, button, modifiers):
        if self.__drag_handle_pos is not None:
            self.setPosition(self.position() + rel)
            return True

        #print("mouseMotionEvent(%s, %s, %s, %s)" % (pos, rel, button, modifiers))
        return super().mouseMotionEvent(pos, rel, button, modifiers)


class GLGraph(nanogui.Widget):
    def __init__(self, parent):
        super().__init__(parent)

        self.__nodes = []
        n1 = Node(self, "Node 1")
        n1.setPosition((100, 200))
        n1.setSize((200, 100))
        self.__nodes.append(n1)

        n2 = Node(self, "Node 2")
        n2.setPosition((400, 250))
        n2.setSize((200, 100))
        self.__nodes.append(n2)

        self.__connections = []
        self.__connections.append((n1, 200, 45, n2, 0, 45))
        self.__connections.append((n1, 200, 55, n2, 0, 55))

        self.__zoom = 1.0

    def scrollEvent(self, pos, rel):
        if rel[1] > 0:
            self.__zoom *= 1.1
        else:
            self.__zoom /= 1.1

        return super().scrollEvent(pos, rel)

    def draw(self, ctx):
        ctx.Save()
        try:
            ctx.Translate(*self.position())
            ctx.Scale(self.__zoom, self.__zoom)

            for n1, x1, y1, n2, x2, y2 in self.__connections:
                p1 = n1.position() + (x1, y1)
                p2 = n2.position() + (x2, y2)

                cpos = (min(100, abs(p2[0] - p1[0]) / 2), 0)

                ctx.BeginPath()
                ctx.StrokeWidth(2.0)
                ctx.StrokeColor(nanogui.Color(0.0, 0.0, 0.0, 1.0))
                ctx.MoveTo(*p1)
                ctx.BezierTo(*(p1 + cpos), *(p2 - cpos), *p2)
                ctx.Stroke()

            for node in self.__nodes:
                node.draw(ctx)

        finally:
            ctx.Restore()

class MainScreen(nanogui.Screen):
    def __init__(self):
        super().__init__((1024, 768), "GL Graph")

        layout = nanogui.AdvancedGridLayout([0], [0, 0, 0])
        layout.setColStretch(0, 1.0)
        layout.setRowStretch(1, 1.0)
        self.setLayout(layout)

        toolbar = nanogui.Widget(self)
        toolbar.setLayout(nanogui.BoxLayout(
            nanogui.Orientation.Horizontal, nanogui.Alignment.Minimum, 0, 2))
        nanogui.Button(toolbar, "load")
        nanogui.Button(toolbar, "save")

        layout.setAnchor(toolbar, nanogui.AdvancedGridLayout.Anchor(0, 0))

        self.graph = GLGraph(self)
        layout.setAnchor(self.graph, nanogui.AdvancedGridLayout.Anchor(0, 1))

        self.statusbar = nanogui.Label(self, "Hello")
        layout.setAnchor(self.statusbar, nanogui.AdvancedGridLayout.Anchor(0, 2))

        self.performLayout()
        self.drawAll()
        self.setVisible(True)

    def resizeEvent(self, *args):
        self.performLayout()
        return super().resizeEvent(*args)


nanogui.init()
try:
    screen = MainScreen()
    nanogui.mainloop()

except Exception:
    traceback.print_exc()

finally:
    # nanogui.shutdown() SEGFAULTs
    os._exit(0)
