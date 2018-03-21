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

add_library(testdata-lv2-ui-gtk2-plugin MODULE ui-gtk2.c)
set_target_properties(testdata-lv2-ui-gtk2-plugin PROPERTIES
  PREFIX ""
  OUTPUT_NAME ui-gtk2
)

add_library(testdata-lv2-ui-gtk2-ui MODULE ui-gtk2-ui.c)
target_include_directories(testdata-lv2-ui-gtk2-ui PRIVATE ${GTK2_INCLUDE_DIRS})
target_link_libraries(testdata-lv2-ui-gtk2-ui PRIVATE ${GTK2_LIBRARIES})
set_target_properties(testdata-lv2-ui-gtk2-ui PROPERTIES
  PREFIX ""
  OUTPUT_NAME ui-gtk2-ui
)

static_file(manifest.ttl)
static_file(ui-gtk2.ttl)

add_custom_target(
  testdata-lv2-ui-gtk2-data ALL
  DEPENDS
    manifest.ttl
    ui-gtk2.ttl
)
