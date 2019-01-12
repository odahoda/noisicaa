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

add_python_package(
  model_base.py
  model_base_test.py
  clef.py
  color.py
  key_signature.py
  key_signature_test.py
  pos2f.py
  pitch.py
  pitch_test.py
  sizef.py
  time_signature.py
  time_signature_test.py
  project.py
)

py_proto(model_base.proto)
py_proto(model_base_test.proto)
py_proto(project.proto)
