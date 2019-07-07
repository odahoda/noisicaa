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

#include "lv2/lv2plug.in/ns/ext/midi/midi.h"

#include "noisicaa/audioproc/public/processor_message.pb.h"
#include "noisicaa/host_system/host_system.h"
#include "noisicaa/builtin_nodes/processor_message_registry.pb.h"
#include "noisicaa/builtin_nodes/midi_source/processor.h"

namespace noisicaa {

ProcessorMidiSource::ProcessorMidiSource(
    const string& realm_name, const string& node_id, HostSystem *host_system,
    const pb::NodeDescription& desc)
  : Processor(
      realm_name, node_id, "noisicaa.audioproc.engine.processor.midi_source", host_system, desc),
    _next_config(nullptr),
    _current_config(nullptr),
    _old_config(nullptr),
    _config{"", -1} {}

Status ProcessorMidiSource::setup_internal() {
  RETURN_IF_ERROR(Processor::setup_internal());

  return Status::Ok();
}

void ProcessorMidiSource::cleanup_internal() {
  Config* config = _next_config.exchange(nullptr);
  if (config != nullptr) {
    delete config;
  }
  config = _current_config.exchange(nullptr);
  if (config != nullptr) {
    delete config;
  }
  config = _old_config.exchange(nullptr);
  if (config != nullptr) {
    delete config;
  }

  Processor::cleanup_internal();
}

Status ProcessorMidiSource::handle_message_internal(pb::ProcessorMessage* msg) {
  unique_ptr<pb::ProcessorMessage> msg_ptr(msg);
  if (msg->HasExtension(pb::midi_source_update)) {
    const pb::MidiSourceUpdate& m = msg->GetExtension(pb::midi_source_update);
    if (m.has_device_uri()) {
      _config.device_uri = m.device_uri();
    }
    if (m.has_channel_filter()) {
      _config.channel_filter = m.channel_filter();
    }
    return update_config();
  } else if (msg->HasExtension(pb::midi_source_event)) {
    const pb::MidiSourceEvent& m = msg->GetExtension(pb::midi_source_event);

    ClientMessage cm;
    memmove(cm.midi, m.midi().c_str(), 3);
    if (!_client_messages.push(cm)) {
      _logger->error("Failed to push MIDI event to queue.");
    }
    return Status::Ok();
  }

  return Processor::handle_message_internal(msg_ptr.release());
}

Status ProcessorMidiSource::update_config() {
  // Discard any next config, which hasn't been picked up by the audio thread.
  Config* prev_next_config = _next_config.exchange(nullptr);
  if (prev_next_config != nullptr) {
    delete prev_next_config;
  }

  // Discard config, which the audio thread doesn't use anymore.
  Config* old_config = _old_config.exchange(nullptr);
  if (old_config != nullptr) {
    delete old_config;
  }

  // Create the new config.
  unique_ptr<Config> config(new Config());
  config->device_uri = _config.device_uri;
  config->channel_filter = _config.channel_filter;

  // Make the new config the next one for the audio thread.
  prev_next_config = _next_config.exchange(config.release());
  assert(prev_next_config == nullptr);

  return Status::Ok();
}

Status ProcessorMidiSource::process_block_internal(BlockContext* ctxt, TimeMapper* time_mapper) {
  Config* config = _next_config.exchange(nullptr);
  if (config != nullptr) {
    Config* old_config = _current_config.exchange(config);
    old_config = _old_config.exchange(old_config);
    assert(old_config == nullptr);
  }

  config = _current_config.load();
  if (config == nullptr) {
    // No config yet, just clear my output ports.
    clear_all_outputs();
    return Status::Ok();
  }

  if (ctxt->input_events == nullptr) {
    // Backend produces no event.
    clear_all_outputs();
    return Status::Ok();
  }

  LV2_Atom_Forge forge;
  lv2_atom_forge_init(&forge, &_host_system->lv2->urid_map);

  LV2_Atom_Forge_Frame frame;
  lv2_atom_forge_set_buffer(&forge, _buffers[0]->data(), 10240);
  lv2_atom_forge_sequence_head(&forge, &frame, _host_system->lv2->urid.atom_frame_time);

  ClientMessage cm;
  while (_client_messages.pop(cm)) {
    lv2_atom_forge_frame_time(&forge, 0);
    lv2_atom_forge_atom(&forge, 3, _host_system->lv2->urid.midi_event);
    lv2_atom_forge_write(&forge, cm.midi, 3);
  }

  LV2_Atom_Event* event = lv2_atom_sequence_begin(&ctxt->input_events->body);
  while (!lv2_atom_sequence_is_end(&ctxt->input_events->body, ctxt->input_events->atom.size, event)) {
    LV2_Atom_Tuple* tup = (LV2_Atom_Tuple*)&event->body;
    uint8_t* body = ((uint8_t*)tup) + sizeof(LV2_Atom_Tuple);
    uint32_t size = tup->atom.size;

    LV2_Atom* it = lv2_atom_tuple_begin(tup);
    assert(!lv2_atom_tuple_is_end(body, size, it));
    assert(it->type == _host_system->lv2->urid.atom_string);
    const char* uri = (const char*)LV2_ATOM_CONTENTS(LV2_Atom_String, it);

    it = lv2_atom_tuple_next(it);
    assert(!lv2_atom_tuple_is_end(body, size, it));
    assert(it->type == _host_system->lv2->urid.midi_event);
    const uint8_t* midi = (const uint8_t*)LV2_ATOM_CONTENTS(LV2_Atom_String, it);

    it = lv2_atom_tuple_next(it);
    assert(lv2_atom_tuple_is_end(body, size, it));

    bool accept = false;
    if (strcmp(uri, config->device_uri.c_str()) == 0) {
      accept = true;
    }

    if (accept && config->channel_filter >= 0) {
      accept = lv2_midi_is_voice_message(midi) && (midi[0] & 0x0f) == config->channel_filter;
    }

    if (accept) {
      lv2_atom_forge_frame_time(&forge, event->time.frames);
      lv2_atom_forge_atom(&forge, 3, _host_system->lv2->urid.midi_event);
      lv2_atom_forge_write(&forge, midi, 3);
    }

    event = lv2_atom_sequence_next(event);
  }

  lv2_atom_forge_pop(&forge, &frame);

  return Status::Ok();
}

}
