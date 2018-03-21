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

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "lv2/lv2plug.in/ns/lv2core/lv2.h"
#include "lv2/lv2plug.in/ns/ext/atom/util.h"
#include "lv2/lv2plug.in/ns/ext/urid/urid.h"
#include "lv2/lv2plug.in/ns/ext/midi/midi.h"

#define PLUGIN_URI "http://noisicaa.odahoda.de/plugins/test-ui-gtk2"

typedef enum {
  AUDIO_INPUT  = 0,
  AUDIO_OUTPUT = 1,
  CONTROL = 2,
} PortIndex;

typedef struct {
  const float* audio_in;
  float*       audio_out;
  const float* control;

  LV2_URID_Map*  map;
} Plugin;

static LV2_Handle instantiate(
    const LV2_Descriptor* descriptor,
    double rate,
    const char* bundle_path,
    const LV2_Feature* const* features) {
  Plugin* self = (Plugin*)calloc(1, sizeof(Plugin));

  for (int i = 0 ; features[i] ; ++i) {
    if (!strcmp(features[i]->URI, LV2_URID__map)) {
      self->map = (LV2_URID_Map*)features[i]->data;
    }
  }
  if (self->map == NULL) {
    fprintf(stderr, "map feature is missing.\n");
    free(self);
    return NULL;
  }

  return (LV2_Handle)self;
}

static void connect_port(LV2_Handle instance, uint32_t port, void* data) {
  Plugin* self = (Plugin*)instance;

  switch ((PortIndex)port) {
  case AUDIO_INPUT:
    self->audio_in = (const float*)data;
    break;
  case AUDIO_OUTPUT:
    self->audio_out = (float*)data;
    break;
  case CONTROL:
    self->control = (float*)data;
    break;
  }
}

static void activate(LV2_Handle instance) {}

static void run(LV2_Handle instance, uint32_t block_size) {
  const Plugin* self = (const Plugin*)instance;

  float control = *self->control;
  const float* in = self->audio_in;
  float* out = self->audio_out;
  for(uint32_t i = 0 ; i < block_size ; ++i) {
    *out++ = control * *in++;
  }
}

static void deactivate(LV2_Handle instance) {}

static void cleanup(LV2_Handle instance) {
  free(instance);
}

static const void* extension_data(const char* uri) {
  return NULL;
}

static const LV2_Descriptor descriptor = {
	PLUGIN_URI,
	instantiate,
	connect_port,
	activate,
	run,
	deactivate,
	cleanup,
	extension_data
};

LV2_SYMBOL_EXPORT const LV2_Descriptor* lv2_descriptor(uint32_t index) {
  switch (index) {
  case 0:  return &descriptor;
  default: return NULL;
  }
}
