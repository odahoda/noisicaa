/*
 * @begin:license
 *
 * Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License along
 * with this program; if not, write to the Free Software Foundation, Inc.,
 * 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
 *
 * @end:license
 */

#ifndef _TESTDATA_LV2_UI_GTK_H
#define _TESTDATA_LV2_UI_GTK_H

#include <stdint.h>
#include "lv2/lv2plug.in/ns/ext/urid/urid.h"

#define PLUGIN_URI "http://noisicaa.odahoda.de/plugins/test-ui-gtk2"

typedef struct {
  uint32_t magic;

  const float* audio_in;
  float*       audio_out;
  const float* control;

  LV2_URID_Map*  map;
} Plugin;

#endif
