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

#include <stdlib.h>
#include <string.h>
#include "ladspa.h"

typedef enum {
  AUDIO_OUTPUT = 0,
} PortIndex;

typedef struct {
  float* audio_out;
} Plugin;

LADSPA_Handle instantiate(const LADSPA_Descriptor* descriptor, unsigned long sample_rate) {
  Plugin* plugin = (Plugin*)calloc(1, sizeof(Plugin));
  return plugin;
}

void connect_port(LADSPA_Handle handle, unsigned long port, LADSPA_Data* data) {
  Plugin* self = (Plugin*)handle;

  switch (port) {
  case AUDIO_OUTPUT:
    self->audio_out = (float*)data;
    break;
  }
}

void run(LADSPA_Handle handle, unsigned long block_size) {
  abort();
}

void cleanup(LADSPA_Handle handle) {
  free(handle);
}

static const LADSPA_PortDescriptor port_descriptors[] = {
  LADSPA_PORT_OUTPUT | LADSPA_PORT_AUDIO,
};

static const char* port_names[] = {
  "audio_out",
};

static const LADSPA_PortRangeHint port_range_hints[] = {
  0,
};

static const LADSPA_Descriptor descriptor = {
  .UniqueID = 2,
  .Label = "crasher",
  .Properties = LADSPA_PROPERTY_REALTIME | LADSPA_PROPERTY_HARD_RT_CAPABLE,
  .Name = "Test plugin 'crasher'",
  .Maker = "Ben Niemann",
  .Copyright = "http://opensource.org/licenses/GPL-2.0",
  .PortCount = 1,
  .PortDescriptors = port_descriptors,
  .PortNames = port_names,
  .PortRangeHints = port_range_hints,
  .ImplementationData = NULL,
  .instantiate = instantiate,
  .connect_port = connect_port,
  .activate = NULL,
  .run = run,
  .run_adding = NULL,
  .set_run_adding_gain = NULL,
  .deactivate = NULL,
  .cleanup = cleanup,
};

const LADSPA_Descriptor* ladspa_descriptor(unsigned long idx) {
  switch (idx) {
  case 0:  return &descriptor;
  default: return NULL;
  }
}
