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

macro(render_wav src dest)
  add_custom_command(
    OUTPUT ${dest}
    COMMAND LD_LIBRARY_PATH=$ENV{VIRTUAL_ENV}/lib csound -o${dest} ${CMAKE_CURRENT_LIST_DIR}/${src}
    DEPENDS ${CMAKE_CURRENT_LIST_DIR}/${src}
  )
endmacro(render_wav)

macro(mksf2 src dest)
  add_custom_command(
    OUTPUT ${dest}
    COMMAND PYTHONPATH=${CMAKE_SOURCE_DIR} python -m noisidev.mksf2 --search_paths=. --output=${dest} ${CMAKE_CURRENT_LIST_DIR}/${src}
    DEPENDS ${CMAKE_CURRENT_LIST_DIR}/${src}
  )
endmacro(mksf2)

static_file(kick-gettinglaid.wav)
static_file(future-thunder1.wav)
static_file(test1.wav)

render_wav(kick.csnd kick.wav)
render_wav(hihat.csnd hihat.wav)
render_wav(snare.csnd snare.wav)
render_wav(organ.csnd organ.wav)

mksf2(sf2test.yaml sf2test.sf2)

static_file(abc/all-around-my-hat.abc)
static_file(abc/sonata-i.abc)

static_file(symbol.svg)

add_custom_target(
  testdata ALL
  DEPENDS
    kick-gettinglaid.wav
    future-thunder1.wav
    test1.wav
    kick.wav
    hihat.wav
    snare.wav
    organ.wav
    sf2test.sf2
    abc/all-around-my-hat.abc
    abc/sonata-i.abc
    symbol.svg
)

add_subdirectory(lv2/test-passthru.lv2)
