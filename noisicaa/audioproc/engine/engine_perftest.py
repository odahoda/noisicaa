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

# import logging
# import os.path

# from noisidev import perf_stats
# from noisidev import profutil
# from noisidev import unittest

# from .. import backend
# from .. import nodes
# from . import engine

# logger = logging.getLogger(__name__)


# class TestBackend(backend.Backend):
#     def __init__(self, *, num_frames=1000, skip_first=10):
#         super().__init__()

#         self.__frame_num = 0
#         self.__num_frames = num_frames
#         self.__skip_first = skip_first
#         self.frame_times = []

#     def begin_frame(self, ctxt):
#         super().begin_frame(ctxt)
#         ctxt.duration = 128
#         ctxt.perf.start_span('frame')
#         if self.__frame_num >= self.__num_frames:
#             self.stop()
#             return
#         self.__frame_num += 1

#     def end_frame(self):
#         self.ctxt.perf.end_span()

#         if not self.stopped:
#             topspan = self.ctxt.perf.serialize().spans[0]
#             assert topspan.parentId == 0
#             assert topspan.name == 'frame'
#             duration = (topspan.endTimeNSec - topspan.startTimeNSec) / 1000.0
#             if self.__frame_num > self.__skip_first:
#                 self.frame_times.append(duration)

#         super().end_frame()

#     def output(self, channel, samples):
#         pass


# class EnginePerfTest(unittest.TestCase):

#     def test_fluidsynth(self):
#         vm = engine.Engine()
#         try:
#             vm.setup(start_thread=False)

#             sink = nodes.Sink()
#             sink.setup()
#             vm.add_node(sink)

#             for idx in range(3):
#                 node = nodes.FluidSynthSource(
#                     id='node%d' % idx,
#                     soundfont_path='/usr/share/sounds/sf2/TimGM6mb.sf2', bank=0, preset=idx)
#                 node.setup()
#                 vm.add_node(node)
#                 sink.inputs['in:left'].connect(node.outputs['out:left'])
#                 sink.inputs['in:right'].connect(node.outputs['out:right'])

#             vm.update_spec()

#             be = TestBackend()
#             vm.setup_backend(be)

#             profutil.profile(self.id(), vm.vm_loop)

#             perf_stats.write_frame_stats(
#                 os.path.splitext(os.path.basename(__file__))[0],
#                 '.'.join(self.id().split('.')[-2:]),
#                 be.frame_times)

#         finally:
#             vm.cleanup()
