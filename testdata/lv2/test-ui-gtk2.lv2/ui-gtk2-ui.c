/*
 * @begin:license
 *
 * Copyright (c) 2015-2019, Benjamin Niemann <pink@odahoda.de>
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

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <gtk/gtk.h>
#include "lv2/lv2plug.in/ns/ext/urid/urid.h"
#include "lv2/lv2plug.in/ns/ext/instance-access/instance-access.h"
#include "lv2/lv2plug.in/ns/extensions/ui/ui.h"

#include "ui-gtk2.h"

#define UI_URI PLUGIN_URI "#ui"

typedef struct {
  LV2_URID_Map* map;

  LV2UI_Write_Function write;
  LV2UI_Controller controller;

  GtkWidget* box;
  GtkWidget* scale;
  guint timeout;
} PluginUI;

static gboolean on_value_changed(GtkWidget* widget, gpointer data) {
  PluginUI* ui = (PluginUI*)data;
  float value = gtk_range_get_value(GTK_RANGE(widget));
  ui->write(ui->controller, 2, sizeof(float), 0, &value);
  return TRUE;
}

static gboolean on_timer(GtkWidget* widget) {
  gdouble value = gtk_range_get_value(GTK_RANGE(widget));
  value = fmin(1.0, value + 0.1);
  gtk_range_set_value(GTK_RANGE(widget), value);
  return (value < 1.0);
}

static LV2UI_Handle instantiate(
    const LV2UI_Descriptor* descriptor,
    const char* plugin_uri,
    const char* bundle_path,
    LV2UI_Write_Function write_function,
    LV2UI_Controller controller,
    LV2UI_Widget* widget,
    const LV2_Feature* const* features) {
  PluginUI* ui = (PluginUI*)calloc(1, sizeof(PluginUI));
  if (!ui) {
    fprintf(stderr, "out of memory\n");
    return NULL;
  }

  ui->map = NULL;
  *widget = NULL;

  Plugin* instance = NULL;

  for (int i = 0; features[i]; ++i) {
    if (!strcmp(features[i]->URI, LV2_URID_URI "#map")) {
      ui->map = (LV2_URID_Map*)features[i]->data;
    } else if (!strcmp(features[i]->URI, LV2_INSTANCE_ACCESS_URI)) {
      instance = (Plugin*)features[i]->data;
    }
  }

  if (!ui->map) {
    fprintf(stderr, "map feature missing\n");
    free(ui);
    return NULL;
  }

  if (!instance) {
    fprintf(stderr, "instance-access feature missing\n");
    free(ui);
    return NULL;
  }

  if (instance->magic != 0x532643f1) {
    fprintf(stderr, "invalid instance pointer\n");
    free(ui);
    return NULL;
  }

  ui->write = write_function;
  ui->controller = controller;

  ui->scale = gtk_hscale_new_with_range(0.0, 1.0, 0.05);
  gtk_widget_set_size_request(ui->scale, 400, 50);
  g_signal_connect(G_OBJECT(ui->scale), "value-changed", G_CALLBACK(on_value_changed), ui);

  ui->box = gtk_vbox_new(FALSE, 0);
  gtk_box_pack_start(GTK_BOX(ui->box), ui->scale, TRUE, TRUE, 0);

  ui->timeout = g_timeout_add(50, (GSourceFunc)on_timer, (gpointer)ui->scale);

  *widget = ui->box;

  return ui;
}

static void cleanup(LV2UI_Handle handle) {
  PluginUI* ui = (PluginUI*)handle;
  g_source_remove(ui->timeout);
  gtk_widget_destroy(ui->scale);
  gtk_widget_destroy(ui->box);
  free(ui);
}

static void port_event(
    LV2UI_Handle handle,
    uint32_t port_index,
    uint32_t buffer_size,
    uint32_t protocol,
    const void* buffer) {}

static const LV2UI_Descriptor descriptor = {
  UI_URI,
  instantiate,
  cleanup,
  port_event,
  NULL
};

LV2_SYMBOL_EXPORT const LV2UI_Descriptor* lv2ui_descriptor(uint32_t index) {
  switch (index) {
  case 0:
    return &descriptor;
  default:
    return NULL;
  }
}
