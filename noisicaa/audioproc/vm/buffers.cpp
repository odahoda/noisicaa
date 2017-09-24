#include <stdlib.h>
#include <string.h>
#include "lv2/lv2plug.in/ns/ext/atom/forge.h"
#include "lv2/lv2plug.in/ns/ext/urid/urid.h"
#include "noisicaa/audioproc/vm/buffers.h"
#include "noisicaa/audioproc/vm/host_data.h"

namespace noisicaa {

uint32_t Float::size(HostData* host_data, uint32_t block_size) const {
  return sizeof(float);
}

Status Float::clear_buffer(HostData* host_data, uint32_t block_size, BufferPtr buf) const {
  float* ptr = (float*)buf;
  ptr[0] = 0.0;
  return Status::Ok();
}

Status Float::mix_buffers(HostData* host_data, uint32_t block_size, const BufferPtr buf1, BufferPtr buf2) const {
  float* ptr1 = (float*)buf1;
  float* ptr2 = (float*)buf2;
  ptr2[0] += ptr1[0];
  return Status::Ok();
}

Status Float::mul_buffer(HostData* host_data, uint32_t block_size, BufferPtr buf, float factor) const {
  float* ptr = (float*)buf;
  ptr[0] *= factor;
  return Status::Ok();
}

uint32_t FloatAudioBlock::size(HostData* host_data, uint32_t block_size) const {
  return block_size * sizeof(float);
}

Status FloatAudioBlock::clear_buffer(HostData* host_data, uint32_t block_size, BufferPtr buf) const {
  float* ptr = (float*)buf;
  for (uint32_t i = 0 ; i < block_size ; ++i) {
    *ptr++ = 0.0;
  }
  return Status::Ok();
}

Status FloatAudioBlock::mix_buffers(HostData* host_data, uint32_t block_size, const BufferPtr buf1, BufferPtr buf2) const {
  float* ptr1 = (float*)buf1;
  float* ptr2 = (float*)buf2;
  for (uint32_t i = 0 ; i < block_size ; ++i) {
    *ptr2++ += *ptr1++;
  }
  return Status::Ok();
}

Status FloatAudioBlock::mul_buffer(HostData* host_data, uint32_t block_size, BufferPtr buf, float factor) const {
  float* ptr = (float*)buf;
  for (uint32_t i = 0 ; i < block_size ; ++i) {
    *ptr++ *= factor;
  }
  return Status::Ok();
}

uint32_t AtomData::size(HostData* host_data, uint32_t block_size) const {
  return 10240;
}

Status AtomData::clear_buffer(HostData* host_data, uint32_t block_size, BufferPtr buf) const {
  memset(buf, 0, 10240);

  LV2_Atom_Forge forge;
  lv2_atom_forge_init(&forge, &host_data->lv2->urid_map);

  LV2_Atom_Forge_Frame frame;
  lv2_atom_forge_set_buffer(&forge, buf, 10240);

  lv2_atom_forge_sequence_head(&forge, &frame, host_data->lv2->urid.atom_frame_time);
  lv2_atom_forge_pop(&forge, &frame);

  return Status::Ok();
}

Status AtomData::mix_buffers(HostData* host_data, uint32_t block_size, const BufferPtr buf1, BufferPtr buf2) const {
  LV2_Atom_Sequence* seq1 = (LV2_Atom_Sequence*)buf1;
  if (seq1->atom.type != host_data->lv2->urid.atom_sequence) {
    return Status::Error("Excepted sequence, got %d.", seq1->atom.type);
  }
  LV2_Atom_Event* event1 = lv2_atom_sequence_begin(&seq1->body);

  LV2_Atom_Sequence* seq2 = (LV2_Atom_Sequence*)buf2;
  if (seq1->atom.type != host_data->lv2->urid.atom_sequence) {
    return Status::Error("Excepted sequence, got %d.", seq2->atom.type);
  }
  LV2_Atom_Event* event2 = lv2_atom_sequence_begin(&seq2->body);

  LV2_Atom_Forge forge;
  lv2_atom_forge_init(&forge, &host_data->lv2->urid_map);

  uint8_t merged[10240];
  memset(merged, 0, 10240);
  lv2_atom_forge_set_buffer(&forge, merged, 10240);

  LV2_Atom_Forge_Frame frame;
  lv2_atom_forge_sequence_head(&forge, &frame, host_data->lv2->urid.atom_frame_time);

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

Status AtomData::mul_buffer(HostData* host_data, uint32_t block_size, BufferPtr buf, float factor) const {
  return Status::Error("Operation not supported for AtomData");
}

Buffer::Buffer(HostData* host_data, const BufferType* type)
  : _type(type),
    _host_data(host_data),
    _block_size(0),
    _data(nullptr),
    _size(0) {
}

Buffer::~Buffer() {}

Status Buffer::allocate(uint32_t block_size) {
  if (block_size > 0) {
    uint32_t size = _type->size(_host_data, block_size);
    if (_size == size) {
      return Status::Ok();
    }

    unique_ptr<uint8_t> data(new uint8_t[size]);
    if (data.get() == nullptr) {
      return Status::Error("Failed to allocate %d bytes.", size);
    }

    Status status = _type->clear_buffer(_host_data, block_size, data.get());
    if (status.is_error()) { return status; }

    _block_size = block_size;
    _size = size;
    _data.reset(data.release());
  }

  return Status::Ok();
}

Status Buffer::clear() {
  // assert _block_size > 0
  return _type->clear_buffer(_host_data, _block_size, _data.get());
}

Status Buffer::mix(const Buffer* other) {
  // assert _block_size > 0
  // assert other._block_size == _block_size
  // assert other._type == _type
  return _type->mix_buffers(_host_data, _block_size, other->_data.get(), _data.get());
}

Status Buffer::mul(float factor) {
  // assert _block_size > 0
  return _type->mul_buffer(_host_data, _block_size, _data.get(), factor);
}
}  // namespace noisicaa
