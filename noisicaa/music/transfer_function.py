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
from typing import Any

from noisicaa import audioproc
from . import model_base
from . import _model
from . import model_pb2

logger = logging.getLogger(__name__)


class TransferFunction(_model.TransferFunction, model_base.ProjectChild):
    FIXED = model_pb2.TransferFunction.FIXED
    LINEAR = model_pb2.TransferFunction.LINEAR
    GAMMA = model_pb2.TransferFunction.GAMMA

    def create(
            self, *,
            input_min: float = 0.0,
            input_max: float = 1.0,
            output_min: float = 0.0,
            output_max: float = 1.0,
            type: int = model_pb2.TransferFunction.FIXED,  # pylint: disable=redefined-builtin
            fixed_value: float = 0.5,
            linear_left_value: float = 0.0,
            linear_right_value: float = 1.0,
            gamma_value: float = 1.0,
            **kwargs: Any
    ) -> None:
        super().create(**kwargs)

        self.input_min = input_min
        self.input_max = input_max
        self.output_min = output_min
        self.output_max = output_max
        self.type = type
        self.fixed_value = fixed_value
        self.linear_left_value = linear_left_value
        self.linear_right_value = linear_right_value
        self.gamma_value = gamma_value

    def get_function_spec(self) -> audioproc.TransferFunctionSpec:
        spec = audioproc.TransferFunctionSpec()
        spec.input_min = self.input_min
        spec.input_max = self.input_max
        spec.output_min = self.output_min
        spec.output_max = self.output_max
        if self.type == model_pb2.TransferFunction.FIXED:
            spec.fixed.value = self.fixed_value
        elif self.type == model_pb2.TransferFunction.LINEAR:
            spec.linear.left_value = self.linear_left_value
            spec.linear.right_value = self.linear_right_value
        elif self.type == model_pb2.TransferFunction.GAMMA:
            spec.gamma.value = self.gamma_value
        else:
            raise ValueError(self.type)

        return spec
