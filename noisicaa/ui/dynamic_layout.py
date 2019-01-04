#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
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

import math
import logging
from typing import Any, List, Sequence, Iterator

from PyQt5.QtCore import Qt
from PyQt5 import QtCore
from PyQt5 import QtWidgets

logger = logging.getLogger(__name__)


class DynamicLayoutItem(object):
    def __init__(self, stretch: int = 0) -> None:
        super().__init__()
        self.__stretch = stretch

    def stretch(self) -> int:
        return self.__stretch

    def widgets(self) -> Iterator[QtWidgets.QWidget]:
        raise NotImplementedError

    def maxPriority(self) -> int:
        raise NotImplementedError

    def hasContent(self, maxPriority: int) -> bool:
        raise NotImplementedError

    def setVisible(self, visible: bool) -> None:
        raise NotImplementedError

    def minimumSize(self, maxPriority: int) -> QtCore.QSize:
        raise NotImplementedError

    def setGeometry(self, rect: QtCore.QRect, maxPriority: int) -> None:
        raise NotImplementedError


class Widget(DynamicLayoutItem):
    def __init__(self, widget: QtWidgets.QWidget, priority: int = 0, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__priority = priority
        self.__widget = widget

    def widgets(self) -> Iterator[QtWidgets.QWidget]:
        yield self.__widget

    def maxPriority(self) -> int:
        return self.__priority

    def setGeometry(self, rect: QtCore.QRect, maxPriority: int) -> None:
        self.__widget.setGeometry(rect)

    def hasContent(self, maxPriority: int) -> bool:
        return self.__priority <= maxPriority

    def setVisible(self, visible: bool) -> None:
        self.__widget.setVisible(visible)

    def minimumSize(self, maxPriority: int) -> QtCore.QSize:
        if self.__priority > maxPriority:
            return QtCore.QSize(0, 0)

        size = self.__widget.minimumSizeHint()
        if size is not None:
            return size

        size = self.__widget.minimumSize()
        if size is not None:
            return size

        return QtCore.QSize(0, 0)


class Container(DynamicLayoutItem):  # pylint: disable=abstract-method
    def __init__(self, *children: DynamicLayoutItem, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__children = children

    def children(self) -> Iterator[DynamicLayoutItem]:
        yield from self.__children

    def widgets(self) -> Iterator[QtWidgets.QWidget]:
        for child in self.__children:
            yield from child.widgets()

    def maxPriority(self) -> int:
        return max(child.maxPriority() for child in self.__children)

    def hasContent(self, maxPriority: int) -> bool:
        return any(child.hasContent(maxPriority) for child in self.__children)

    def setVisible(self, visible: bool) -> None:
        if not visible:
            for child in self.__children:
                child.setVisible(visible)


class FirstMatch(Container):
    def minimumSize(self, maxPriority: int) -> QtCore.QSize:
        children = [child for child in self.children() if child.hasContent(maxPriority)]
        if not children:
            return QtCore.QSize(0, 0)

        size = children[0].minimumSize(maxPriority)
        for child in children[1:]:
            child_size = child.minimumSize(maxPriority)
            if child_size.width() < size.width() or child_size.height() < size.height():
                size = child_size

        return size

    def setGeometry(self, rect: QtCore.QRect, maxPriority: int) -> None:
        children = [child for child in self.children() if child.hasContent(maxPriority)]
        if not children:
            self.setVisible(False)
            return

        visible_child = children[-1]
        for child in children:
            child_size = child.minimumSize(maxPriority)
            if child_size.width() <= rect.width() and child_size.height() <= rect.height():
                visible_child = child
                break

        for child in self.children():
            if child is visible_child:
                child.setVisible(True)
                child.setGeometry(rect, maxPriority)
            else:
                child.setVisible(False)


class Box(Container):
    def __init__(
            self,
            *children: DynamicLayoutItem,
            orientation: Qt.Orientation,
            spacing: int = 0,
            **kwargs: Any
    ) -> None:
        super().__init__(*children, **kwargs)

        self.__orientation = orientation
        self.__spacing = spacing

    def orientation(self) -> Qt.Orientation:
        return self.__orientation

    def spacing(self) -> int:
        return self.__spacing

    def _computeSizes(
            self,
            total_size: int,
            children: Sequence[DynamicLayoutItem],
            min_sizes: Sequence[int],
            stretch_weights: Sequence[int]
    ) -> List[int]:
        if sum(stretch_weights) == 0:
            stretch_weights = [1 for _ in children]
        total_stretch_weight = sum(stretch_weights)

        sizes = [min_size for min_size in min_sizes]

        while True:
            stretch_size = max(0, total_size - sum(sizes))
            if stretch_size <= 0:
                break
            remaining = stretch_size
            for idx in range(len(children)):
                add = min(
                    remaining,
                    int(math.ceil(stretch_weights[idx] * stretch_size / total_stretch_weight)))
                sizes[idx] += add
                remaining -= add

        return sizes

    def minimumSize(self, maxPriority: int) -> QtCore.QSize:
        width = 0
        height = 0

        first = True
        for child in self.children():
            if child.hasContent(maxPriority):
                if not first:
                    if self.__orientation == Qt.Horizontal:
                        width += self.spacing()
                    else:
                        height += self.spacing()
                    first = False

                child_size = child.minimumSize(maxPriority)
                if self.__orientation == Qt.Horizontal:
                    width += child_size.width()
                    height = max(height, child_size.height())
                else:
                    width = max(width, child_size.width())
                    height += child_size.height()

        return QtCore.QSize(width, height)

    def setGeometry(self, rect: QtCore.QRect, maxPriority: int) -> None:
        min_sizes = []
        children = []
        stretch_weights = []
        if self.__orientation == Qt.Horizontal:
            total_size = rect.width()
        else:
            total_size = rect.height()

        first = True
        for child in self.children():
            if child.hasContent(maxPriority):
                if not first:
                    total_size -= self.spacing()
                    first = False

                child.setVisible(True)
                if self.__orientation == Qt.Horizontal:
                    child_min_size = child.minimumSize(maxPriority).width()
                else:
                    child_min_size = child.minimumSize(maxPriority).height()
                min_sizes.append(child_min_size)
                children.append(child)
                stretch_weights.append(child.stretch())

            else:
                child.setVisible(False)

        sizes = self._computeSizes(total_size, children, min_sizes, stretch_weights)

        if self.__orientation == Qt.Horizontal:
            pos = rect.left()
        else:
            pos = rect.top()

        for idx, child in enumerate(children):
            if idx > 0:
                pos += self.spacing()

            size = sizes[idx]
            if self.__orientation == Qt.Horizontal:
                child.setGeometry(QtCore.QRect(pos, rect.top(), size, rect.height()), maxPriority)
            else:
                child.setGeometry(QtCore.QRect(rect.left(), pos, rect.width(), size), maxPriority)

            pos += size


class HBox(Box):
    def __init__(self, *children: DynamicLayoutItem, **kwargs: Any) -> None:
        super().__init__(*children, orientation=Qt.Horizontal, **kwargs)


class VBox(Box):
    def __init__(self, *children: DynamicLayoutItem, **kwargs: Any) -> None:
        super().__init__(*children, orientation=Qt.Vertical, **kwargs)


class DynamicLayout(QtWidgets.QLayout):
    def __init__(self, root: DynamicLayoutItem) -> None:
        super().__init__()

        self.__root = root
        self.__widgets = list(QtWidgets.QWidgetItem(widget) for widget in self.__root.widgets())

    def count(self) -> int:
        return len(self.__widgets)

    def addItem(self, item: QtWidgets.QLayoutItem) -> None:
        raise RuntimeError("Can't add items to a DynamicLayout.")

    def itemAt(self, index: int) -> QtWidgets.QLayoutItem:
        try:
            return self.__widgets[index]
        except IndexError:
            return None

    def takeAt(self, index: int) -> QtWidgets.QLayoutItem:
        raise RuntimeError("Can't remove items from a DynamicLayout.")

    def clear(self) -> None:
        self.__widgets.clear()

    def sizeHint(self) -> QtCore.QSize:
        return QtCore.QSize(0, 0)

    def minimumSize(self) -> QtCore.QSize:
        return QtCore.QSize(0, 0)

    def setGeometry(self, rect: QtCore.QRect) -> None:
        priority = self.__root.maxPriority()
        while priority > 0:
            min_size = self.__root.minimumSize(priority)
            if min_size.width() <= rect.width() and min_size.height() <= rect.height():
                break
            priority -= 1

        self.__root.setGeometry(rect, priority)
