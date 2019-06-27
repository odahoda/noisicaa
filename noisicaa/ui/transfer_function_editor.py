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

import logging
from typing import Any, Dict

from PyQt5 import QtWidgets

from noisicaa import core
from noisicaa import music
from noisicaa.ui import ui_base
from noisicaa.ui import property_connector

logger = logging.getLogger(__name__)


class TransferFunctionEditor(ui_base.ProjectMixin, core.AutoCleanupMixin, QtWidgets.QWidget):
    def __init__(
            self, *,
            transfer_function: music.TransferFunction,
            mutation_name_prefix: str,
            **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)

        self.__transfer_function = transfer_function
        self.__mutation_name_prefix = mutation_name_prefix

        self.__stack = QtWidgets.QStackedWidget()
        type_to_stack_index = {}  # type: Dict[int, int]

        self.__fixed_value = QtWidgets.QSpinBox()
        self.__fixed_value.setRange(0, 127)
        self.__fixed_value_connector = property_connector.QSpinBoxConnector(
            self.__fixed_value, self.__transfer_function, 'fixed_value',
            mutation_name='%s: Change fixed value' % self.__mutation_name_prefix,
            context=self.context)
        self.add_cleanup_function(self.__fixed_value_connector.cleanup)

        self.__fixed_params = QtWidgets.QWidget()
        l2 = QtWidgets.QVBoxLayout()
        l2.setContentsMargins(0, 0, 0, 0)
        l2.addWidget(self.__fixed_value)
        self.__fixed_params.setLayout(l2)

        type_to_stack_index[music.TransferFunction.FIXED] = self.__stack.addWidget(
            self.__fixed_params)

        self.__linear_left_value = QtWidgets.QSpinBox()
        self.__linear_left_value.setRange(0, 127)
        self.__linear_left_value_connector = property_connector.QSpinBoxConnector(
            self.__linear_left_value, self.__transfer_function, 'linear_left_value',
            mutation_name='%s: Change linear mapping' % self.__mutation_name_prefix,
            context=self.context)
        self.add_cleanup_function(self.__linear_left_value_connector.cleanup)

        self.__linear_right_value = QtWidgets.QSpinBox()
        self.__linear_right_value.setRange(0, 127)
        self.__linear_right_value_connector = property_connector.QSpinBoxConnector(
            self.__linear_right_value, self.__transfer_function, 'linear_right_value',
            mutation_name='%s: Change linear mapping' % self.__mutation_name_prefix,
            context=self.context)
        self.add_cleanup_function(self.__linear_right_value_connector.cleanup)

        self.__linear_params = QtWidgets.QWidget()
        l3 = QtWidgets.QHBoxLayout()
        l3.setContentsMargins(0, 0, 0, 0)
        l3.addWidget(self.__linear_left_value)
        l3.addWidget(self.__linear_right_value)
        self.__linear_params.setLayout(l3)

        type_to_stack_index[music.TransferFunction.LINEAR] = self.__stack.addWidget(
            self.__linear_params)

        self.__gamma_value = QtWidgets.QDoubleSpinBox()
        self.__gamma_value.setRange(0.1, 10.0)
        self.__gamma_value.setSingleStep(0.1)
        self.__gamma_value_connector = property_connector.QDoubleSpinBoxConnector(
            self.__gamma_value, self.__transfer_function, 'gamma_value',
            mutation_name='%s: Change gamma value' % self.__mutation_name_prefix,
            context=self.context)
        self.add_cleanup_function(self.__gamma_value_connector.cleanup)

        self.__gamma_params = QtWidgets.QWidget()
        l2 = QtWidgets.QVBoxLayout()
        l2.setContentsMargins(0, 0, 0, 0)
        l2.addWidget(self.__gamma_value)
        self.__gamma_params.setLayout(l2)

        type_to_stack_index[music.TransferFunction.GAMMA] = self.__stack.addWidget(
            self.__gamma_params)

        self.__type = QtWidgets.QComboBox()
        self.__type.addItem("Fixed", music.TransferFunction.FIXED)
        self.__type.addItem("Linear", music.TransferFunction.LINEAR)
        self.__type.addItem("Gamma", music.TransferFunction.GAMMA)
        self.__type.currentIndexChanged.connect(
            lambda _: self.__stack.setCurrentIndex(type_to_stack_index[self.__type.currentData()]))
        self.__type_connector = property_connector.QComboBoxConnector[int](
            self.__type, self.__transfer_function, 'type',
            mutation_name='%s: Change function type' % self.__mutation_name_prefix,
            context=self.context)
        self.add_cleanup_function(self.__type_connector.cleanup)

        l1 = QtWidgets.QVBoxLayout()
        l1.setContentsMargins(0, 0, 0, 0)
        l1.addWidget(self.__type)
        l1.addWidget(self.__stack)
        l1.addStretch(1)
        self.setLayout(l1)
