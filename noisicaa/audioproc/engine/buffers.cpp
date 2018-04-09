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
#include <pthread.h>
#include "lv2/lv2plug.in/ns/ext/atom/forge.h"
#include "lv2/lv2plug.in/ns/ext/urid/urid.h"
#include "noisicaa/audioproc/engine/plugin_host.h"
#include "noisicaa/audioproc/engine/buffers.h"
#include "noisicaa/host_system/host_system.h"

namespace noisicaa {

Status BufferType::setup(HostSystem* host_system, BufferPtr buf) const {
  return Status::Ok();
}

void BufferType::cleanup(HostSystem* host_system, BufferPtr buf) const {
}

uint32_t FloatControlValueBuffer::size(HostSystem* host_system) const {
  return sizeof(ControlValue);
}

Status FloatControlValueBuffer::clear_buffer(HostSystem* host_system, BufferPtr buf) const {
  ControlValue* ptr = (ControlValue*)buf;
  ptr->value = 0.0;
  ptr->generation = 0;
  return Status::Ok();
}

Status FloatControlValueBuffer::mix_buffers(
    HostSystem* host_system, const BufferPtr buf1, BufferPtr buf2) const {
  ControlValue* ptr1 = (ControlValue*)buf1;
  ControlValue* ptr2 = (ControlValue*)buf2;
  ptr2->value += ptr1->value;
  ptr2->generation = max(ptr1->generation, ptr2->generation) + 1;
  return Status::Ok();
}

Status FloatControlValueBuffer::mul_buffer(
    HostSystem* host_system, BufferPtr buf, float factor) const {
  ControlValue* ptr = (ControlValue*)buf;
  ptr->value *= factor;
  ptr->generation += 1;
  return Status::Ok();
}

uint32_t FloatAudioBlockBuffer::size(HostSystem* host_system) const {
  return host_system->block_size() * sizeof(float);
}

Status FloatAudioBlockBuffer::clear_buffer(HostSystem* host_system, BufferPtr buf) const {
  float* ptr = (float*)buf;
  for (uint32_t i = 0 ; i < host_system->block_size() ; ++i) {
    *ptr++ = 0.0;
  }
  return Status::Ok();
}

Status FloatAudioBlockBuffer::mix_buffers(
    HostSystem* host_system, const BufferPtr buf1, BufferPtr buf2) const {
  float* ptr1 = (float*)buf1;
  float* ptr2 = (float*)buf2;
  for (uint32_t i = 0 ; i < host_system->block_size() ; ++i) {
    *ptr2++ += *ptr1++;
  }
  return Status::Ok();
}

Status FloatAudioBlockBuffer::mul_buffer(HostSystem* host_system, BufferPtr buf, float factor) const {
  float* ptr = (float*)buf;
  for (uint32_t i = 0 ; i < host_system->block_size() ; ++i) {
    *ptr++ *= factor;
  }
  return Status::Ok();
}

uint32_t AtomDataBuffer::size(HostSystem* host_system) const {
  return 10240;
}

Status AtomDataBuffer::clear_buffer(HostSystem* host_system, BufferPtr buf) const {
  memset(buf, 0, 10240);

  LV2_Atom_Forge forge;
  lv2_atom_forge_init(&forge, &host_system->lv2->urid_map);

  LV2_Atom_Forge_Frame frame;
  lv2_atom_forge_set_buffer(&forge, buf, 10240);

  lv2_atom_forge_sequence_head(&forge, &frame, host_system->lv2->urid.atom_frame_time);
  lv2_atom_forge_pop(&forge, &frame);

  return Status::Ok();
}

Status AtomDataBuffer::mix_buffers(
    HostSystem* host_system, const BufferPtr buf1, BufferPtr buf2) const {
  LV2_Atom_Sequence* seq1 = (LV2_Atom_Sequence*)buf1;
  if (seq1->atom.type != host_system->lv2->urid.atom_sequence) {
    return ERROR_STATUS("Excepted sequence, got %d.", seq1->atom.type);
  }
  LV2_Atom_Event* event1 = lv2_atom_sequence_begin(&seq1->body);

  LV2_Atom_Sequence* seq2 = (LV2_Atom_Sequence*)buf2;
  if (seq1->atom.type != host_system->lv2->urid.atom_sequence) {
    return ERROR_STATUS("Excepted sequence, got %d.", seq2->atom.type);
  }
  LV2_Atom_Event* event2 = lv2_atom_sequence_begin(&seq2->body);

  LV2_Atom_Forge forge;
  lv2_atom_forge_init(&forge, &host_system->lv2->urid_map);

  uint8_t merged[10240];
  memset(merged, 0, 10240);
  lv2_atom_forge_set_buffer(&forge, merged, 10240);

  LV2_Atom_Forge_Frame frame;
  lv2_atom_forge_sequence_head(&forge, &frame, host_system->lv2->urid.atom_frame_time);

  while (!lv2_atom_sequence_is_end(&seq1->body, seq1->atom.size, event1)
         && !lv2_atom_sequence_is_end(&seq2->body, seq2->atom.size, event2)) {
    LV2_Atom_Event* event;
    if (event1->time.frames <= event2->time.frames) {
      event = event1;
      event1 = lv2_atom_sequence_next(event1);
    } else {
      event = event2;
      event2 = lv2_atom_sequence_next(event2);
    }

    lv2_atom_forge_frame_time(&forge, event->time.frames);
    lv2_atom_forge_primitive(&forge, &event->body);
  }

  while (!lv2_atom_sequence_is_end(&seq1->body, seq1->atom.size, event1)) {
    lv2_atom_forge_frame_time(&forge, event1->time.frames);
    lv2_atom_forge_primitive(&forge, &event1->body);
    event1 = lv2_atom_sequence_next(event1);
  }

  while (!lv2_atom_sequence_is_end(&seq2->body, seq2->atom.size, event2)) {
    lv2_atom_forge_frame_time(&forge, event2->time.frames);
    lv2_atom_forge_primitive(&forge, &event2->body);
    event2 = lv2_atom_sequence_next(event2);
  }

  lv2_atom_forge_pop(&forge, &frame);

  memmove(buf2, merged, 10240);

  return Status::Ok();
}

Status AtomDataBuffer::mul_buffer(HostSystem* host_system, BufferPtr buf, float factor) const {
  return ERROR_STATUS("Operation not supported for AtomDataBuffer");
}

uint32_t PluginCondBuffer::size(HostSystem* host_system) const {
  return sizeof(PluginCond);
}

Status PluginCondBuffer::setup(HostSystem* host_system, BufferPtr buf) const {
  PluginCond* pc = (PluginCond*)buf;

  pc->magic = 0x34638a33;
  pc->set = false;

  pthread_mutexattr_t mutexattr;
  RETURN_IF_PTHREAD_ERROR(pthread_mutexattr_init(&mutexattr));
  RETURN_IF_PTHREAD_ERROR(pthread_mutexattr_setpshared(&mutexattr, PTHREAD_PROCESS_SHARED));
  RETURN_IF_PTHREAD_ERROR(pthread_mutex_init(&pc->mutex, &mutexattr));

  pthread_condattr_t condattr;
  RETURN_IF_PTHREAD_ERROR(pthread_condattr_init(&condattr));
  RETURN_IF_PTHREAD_ERROR(pthread_condattr_setpshared(&condattr, PTHREAD_PROCESS_SHARED));
  RETURN_IF_PTHREAD_ERROR(pthread_cond_init(&pc->cond, &condattr));

  return Status::Ok();
}

void PluginCondBuffer::cleanup(HostSystem* host_system, BufferPtr buf) const {
  PluginCond* pc = (PluginCond*)buf;

  pthread_cond_destroy(&pc->cond);
  pthread_mutex_destroy(&pc->mutex);
}

Status PluginCondBuffer::clear_buffer(HostSystem* host_system, const BufferPtr buf) const {
  return ERROR_STATUS("Operation not supported for PluginCondBuffer");
}

Status PluginCondBuffer::mix_buffers(HostSystem* host_system, const BufferPtr buf1, BufferPtr buf2) const {
  return ERROR_STATUS("Operation not supported for PluginCondBuffer");
}

Status PluginCondBuffer::mul_buffer(HostSystem* host_system, BufferPtr buf, float factor) const {
  return ERROR_STATUS("Operation not supported for PluginCondBuffer");
}

Status PluginCondBuffer::set_cond(BufferPtr buf) {
  PluginCond* plugin_cond = (PluginCond*)buf;

  if (plugin_cond->magic != 0x34638a33) {
    return ERROR_STATUS("PluginCondBuffer not initialized.");
  }

  RETURN_IF_PTHREAD_ERROR(pthread_mutex_lock(&plugin_cond->mutex));
  plugin_cond->set = true;
  RETURN_IF_PTHREAD_ERROR(pthread_mutex_unlock(&plugin_cond->mutex));
  RETURN_IF_PTHREAD_ERROR(pthread_cond_signal(&plugin_cond->cond));

  return Status::Ok();
}

Status PluginCondBuffer::clear_cond(BufferPtr buf) {
  PluginCond* plugin_cond = (PluginCond*)buf;

  if (plugin_cond->magic != 0x34638a33) {
    return ERROR_STATUS("PluginCondBuffer not initialized.");
  }

  RETURN_IF_PTHREAD_ERROR(pthread_mutex_lock(&plugin_cond->mutex));
  plugin_cond->set = false;
  RETURN_IF_PTHREAD_ERROR(pthread_mutex_unlock(&plugin_cond->mutex));

  return Status::Ok();
}

Status PluginCondBuffer::wait_cond(BufferPtr buf) {
  PluginCond* plugin_cond = (PluginCond*)buf;

  if (plugin_cond->magic != 0x34638a33) {
    return ERROR_STATUS("PluginCondBuffer not initialized.");
  }

  RETURN_IF_PTHREAD_ERROR(pthread_mutex_lock(&plugin_cond->mutex));
  while (!plugin_cond->set) {
    RETURN_IF_PTHREAD_ERROR(pthread_cond_wait(&plugin_cond->cond, &plugin_cond->mutex));
  }
  RETURN_IF_PTHREAD_ERROR(pthread_mutex_unlock(&plugin_cond->mutex));

  return Status::Ok();
}

Buffer::Buffer(HostSystem* host_system, const BufferType* type, BufferPtr data)
  : _type(type),
    _host_system(host_system),
    _data(data) {}

Buffer::~Buffer() {}

Status Buffer::setup() {
  return _type->setup(_host_system, _data);
}

void Buffer::cleanup() {
  _type->cleanup(_host_system, _data);
}

Status Buffer::clear() {
  return _type->clear_buffer(_host_system, _data);
}

Status Buffer::mix(const Buffer* other) {
  // assert other._type == _type
  return _type->mix_buffers(_host_system, other->_data, _data);
}

Status Buffer::mul(float factor) {
  return _type->mul_buffer(_host_system, _data, factor);
}
}  // namespace noisicaa
