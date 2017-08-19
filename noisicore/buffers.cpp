#include "buffers.h"

#include <stdlib.h>
#include <string.h>
#include "lv2/lv2plug.in/ns/ext/atom/forge.h"
#include "lv2/lv2plug.in/ns/ext/urid/urid.h"
#include "misc.h"

namespace noisicaa {

uint32_t Float::size(uint32_t frame_size) const {
  return sizeof(float);
}

Status Float::clear_buffer(uint32_t frame_size, BufferPtr buf) const {
  float* ptr = (float*)buf;
  ptr[0] = 0.0;
  return Status::Ok();
}

Status Float::mix_buffers(uint32_t frame_size, const BufferPtr buf1, BufferPtr buf2) const {
  float* ptr1 = (float*)buf1;
  float* ptr2 = (float*)buf2;
  ptr2[0] += ptr1[0];
  return Status::Ok();
}

Status Float::mul_buffer(uint32_t frame_size, BufferPtr buf, float factor) const {
  float* ptr = (float*)buf;
  ptr[0] *= factor;
  return Status::Ok();
}

uint32_t FloatAudioFrame::size(uint32_t frame_size) const {
  return frame_size * sizeof(float);
}

Status FloatAudioFrame::clear_buffer(uint32_t frame_size, BufferPtr buf) const {
  float* ptr = (float*)buf;
  for (uint32_t i = 0 ; i < frame_size ; ++i) {
    *ptr++ = 0.0;
  }
  return Status::Ok();
}

Status FloatAudioFrame::mix_buffers(uint32_t frame_size, const BufferPtr buf1, BufferPtr buf2) const {
  float* ptr1 = (float*)buf1;
  float* ptr2 = (float*)buf2;
  for (uint32_t i = 0 ; i < frame_size ; ++i) {
    *ptr2++ += *ptr1++;
  }
  return Status::Ok();
}

Status FloatAudioFrame::mul_buffer(uint32_t frame_size, BufferPtr buf, float factor) const {
  float* ptr = (float*)buf;
  for (uint32_t i = 0 ; i < frame_size ; ++i) {
    *ptr++ *= factor;
  }
  return Status::Ok();
}

AtomData::AtomData(LV2_URID_Map* map)
  : _map(map) {
  _frame_time_urid = _map->map(_map->handle, "http://lv2plug.in/ns/ext/atom#frameTime");
  _sequence_urid = _map->map(_map->handle, "http://lv2plug.in/ns/ext/atom#Sequence");
}

uint32_t AtomData::size(uint32_t frame_size) const {
  return 10240;
}

Status AtomData::clear_buffer(uint32_t frame_size, BufferPtr buf) const {
  memset(buf, 0, 10240);

  LV2_Atom_Forge forge;
  lv2_atom_forge_init(&forge, _map);

  LV2_Atom_Forge_Frame frame;
  lv2_atom_forge_set_buffer(&forge, buf, 10240);

  lv2_atom_forge_sequence_head(&forge, &frame, _frame_time_urid);
  lv2_atom_forge_pop(&forge, &frame);

  return Status::Ok();
}

Status AtomData::mix_buffers(uint32_t frame_size, const BufferPtr buf1, BufferPtr buf2) const {
  LV2_Atom_Sequence* seq1 = (LV2_Atom_Sequence*)buf1;
  if (seq1->atom.type != _sequence_urid) {
    return Status::Error(sprintf("Excepted sequence, got %d.", seq1->atom.type));
  }
  LV2_Atom_Event* event1 = lv2_atom_sequence_begin(&seq1->body);

  LV2_Atom_Sequence* seq2 = (LV2_Atom_Sequence*)buf2;
  if (seq1->atom.type != _sequence_urid) {
    return Status::Error(sprintf("Excepted sequence, got %d.", seq2->atom.type));
  }
  LV2_Atom_Event* event2 = lv2_atom_sequence_begin(&seq2->body);

  LV2_Atom_Forge forge;
  lv2_atom_forge_init(&forge, _map);

  uint8_t merged[10240];
  memset(merged, 0, 10240);
  lv2_atom_forge_set_buffer(&forge, merged, 10240);

  LV2_Atom_Forge_Frame frame;
  lv2_atom_forge_sequence_head(&forge, &frame, _frame_time_urid);

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

Status AtomData::mul_buffer(uint32_t frame_size, BufferPtr buf, float factor) const {
  return Status::Error("Operation not supported for AtomData");
}

Buffer::Buffer(const BufferType* type)
  : _type(type),
    _frame_size(0),
    _data(nullptr),
    _size(0) {
}

Buffer::~Buffer() {
  _free_data();
}

void Buffer::_free_data() {
  if (_data != nullptr) {
    free(_data);
    _data = nullptr;
    _size = 0;
  }
}

Status Buffer::allocate(uint32_t frame_size) {
  _free_data();

  if (frame_size > 0) {
    uint32_t size = _type->size(frame_size);
    BufferPtr data = (BufferPtr)malloc(size);
    if (data == nullptr) {
      return Status::Error(sprintf("Failed to allocate %d bytes.", size));
    }

    Status status = _type->clear_buffer(frame_size, data);
    if (status.is_error()) { return status; }

    _frame_size = frame_size;
    _size = size;
    _data = data;
  }

  return Status::Ok();
}

Status Buffer::clear() {
  // assert _frame_size > 0
  return _type->clear_buffer(_frame_size, _data);
}

Status Buffer::mix(const Buffer* other) {
  // assert _frame_size > 0
  // assert other._frame_size == _frame_size
  // assert other._type == _type
  return _type->mix_buffers(_frame_size, other->_data, _data);
}

Status Buffer::mul(float factor) {
  // assert _frame_size > 0
  return _type->mul_buffer(_frame_size, _data, factor);
}
}  // namespace noisicaa
