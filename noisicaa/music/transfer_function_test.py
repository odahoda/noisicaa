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

from noisidev import unittest
from noisidev import unittest_mixins
from . import model_pb2
from . import transfer_function


class TransferFunctionTest(unittest_mixins.ProjectMixin, unittest.AsyncTestCase):
    async def test_get_function_spec(self):
        with self.project.apply_mutations('test'):
            tf = self.pool.create(
                transfer_function.TransferFunction,
                input_min=-10.0,
                input_max=10.0,
                output_min=0.0,
                output_max=1.0,
                type=model_pb2.TransferFunction.LINEAR,
                linear_left_value=0.1,
                linear_right_value=0.8)

            spec = tf.get_function_spec()
            self.assertAlmostEqual(spec.input_min, -10.0)
            self.assertAlmostEqual(spec.input_max, 10.0)
            self.assertAlmostEqual(spec.output_min, 0.0)
            self.assertAlmostEqual(spec.output_max, 1.0)
            self.assertEqual(spec.WhichOneof('type'), 'linear')
            self.assertAlmostEqual(spec.linear.left_value, 0.1)
            self.assertAlmostEqual(spec.linear.right_value, 0.8)
