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

#include <arpa/inet.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include "lv2/lv2plug.in/ns/lv2core/lv2.h"
#include "lv2/lv2plug.in/ns/ext/atom/atom.h"
#include "lv2/lv2plug.in/ns/ext/state/state.h"
#include "lv2/lv2plug.in/ns/ext/urid/urid.h"

#define PLUGIN_URI "http://noisicaa.odahoda.de/plugins/test-state"

typedef enum {
  AUDIO_INPUT  = 0,
  AUDIO_OUTPUT = 1,
} PortIndex;

typedef struct {
  const float* audio_in;
  float* audio_out;

  LV2_URID_Map* map;
  LV2_URID atom_number_urid;

  uint32_t foo;
  LV2_URID foo_urid;
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

  self->atom_number_urid = self->map->map(self->map->handle, LV2_ATOM__Number);

  self->foo = 0x75391654;
  self->foo_urid = self->map->map(self->map->handle, PLUGIN_URI "#foo");

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
  }
}

static void activate(LV2_Handle instance) {}

static void run(LV2_Handle instance, uint32_t block_size) {
  const Plugin* self = (const Plugin*)instance;

  memmove(self->audio_out, self->audio_in, block_size * sizeof(float));
}

static void deactivate(LV2_Handle instance) {}

static void cleanup(LV2_Handle instance) {
  free(instance);
}

static LV2_State_Status save(
    LV2_Handle instance,
    LV2_State_Store_Function store,
    LV2_State_Handle handle,
    uint32_t flags,
    const LV2_Feature* const* features) {
  const Plugin* self = (const Plugin*)instance;

  LV2_State_Status status;

  uint32_t foo_n = htonl(self->foo);
  status = store(
      handle,
      self->foo_urid,
      &foo_n, sizeof(uint32_t),
      self->atom_number_urid,
      LV2_STATE_IS_POD | LV2_STATE_IS_PORTABLE);
  if (status != LV2_STATE_SUCCESS) { return status; }

  return LV2_STATE_SUCCESS;
}

static LV2_State_Status restore(
    LV2_Handle instance,
    LV2_State_Retrieve_Function retrieve,
    LV2_State_Handle handle,
    uint32_t flags,
    const LV2_Feature* const* features) {
  return LV2_STATE_SUCCESS;
}

static const LV2_State_Interface state_interface = { save, restore };

static const void* extension_data(const char* uri) {
  if (!strcmp(uri, LV2_STATE__interface)) {
    return &state_interface;
  }

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
