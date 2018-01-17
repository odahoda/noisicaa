# @begin:license
#
# Copyright (c) 2015-2017, Benjamin Niemann <pink@odahoda.de>
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

@0x82a31f158cebdce3;

using Cxx = import "/capnp/c++.capnp";
$Cxx.namespace("noisicaa::capnp");

# Absolute imports don't work reliably with Python.
using import "../../core/perf_stats.capnp".PerfStats;

struct Buffer {
  id @0 :Text;
  data @1 :Data;
}

struct BlockData {
  blockSize @0 :UInt32;
  samplePos @1 :UInt64;

  buffers @2 :List(Buffer);
  messages @3 :List(Data);
  perfData @4 :PerfStats;
  timeMap @5 :Data;
}
