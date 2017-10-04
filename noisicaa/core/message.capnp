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

@0xb5afa1e45874d1ef;

using Cxx = import "/capnp/c++.capnp";
$Cxx.namespace("noisicaa::capnp");

enum Key {
  sheetId @0;
  trackId @1;
}

struct Label {
  key @0 :Key;
  value @1 :Text;
}

struct Labelset {
  labels @0 :List(Label);
}

enum Type {
  atom @0;
}

struct Message {
  labelset @0 :Labelset;
  type @1 :Type;
  data @2 :Data;
}
