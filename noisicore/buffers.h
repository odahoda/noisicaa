#ifndef _NOISICORE_BUFFERS_H
#define _NOISICORE_BUFFERS_H

#include <memory>
#include <stdint.h>
#include "lv2/lv2plug.in/ns/ext/atom/forge.h"
#include "lv2/lv2plug.in/ns/ext/urid/urid.h"
#include "status.h"

using std::unique_ptr;

namespace noisicaa {

typedef uint8_t* BufferPtr;

class BufferType {
 public:
  virtual ~BufferType() {}

  virtual uint32_t size(uint32_t frame_size) const = 0;

  virtual Status clear_buffer(uint32_t frame_size, BufferPtr buf) const = 0;
  virtual Status mix_buffers(uint32_t frame_size, const BufferPtr buf1, BufferPtr buf2) const = 0;
  virtual Status mul_buffer(uint32_t frame_size, BufferPtr buf, float factor) const = 0;
};

class Float : public BufferType {
 public:
  uint32_t size(uint32_t frame_size) const override;

  Status clear_buffer(uint32_t frame_size, BufferPtr buf) const override;
  Status mix_buffers(uint32_t frame_size, const BufferPtr buf1, BufferPtr buf2) const override;
  Status mul_buffer(uint32_t frame_size, BufferPtr buf, float factor) const override;
};

class FloatAudioFrame : public BufferType {
 public:
  uint32_t size(uint32_t frame_size) const override;

  Status clear_buffer(uint32_t frame_size, BufferPtr buf) const override;
  Status mix_buffers(uint32_t frame_size, const BufferPtr buf1, BufferPtr buf2) const override;
  Status mul_buffer(uint32_t frame_size, BufferPtr buf, float factor) const override;
};

class AtomData : public BufferType {
 public:
  AtomData(LV2_URID_Map* map);

  uint32_t size(uint32_t frame_size) const override;

  Status clear_buffer(uint32_t frame_size, BufferPtr buf) const override;
  Status mix_buffers(uint32_t frame_size, const BufferPtr buf1, BufferPtr buf2) const override;
  Status mul_buffer(uint32_t frame_size, BufferPtr buf, float factor) const override;

 private:
  LV2_URID_Map* _map;
  LV2_URID _frame_time_urid;
  LV2_URID _sequence_urid;
};

class Buffer {
 public:
  Buffer(const BufferType* type);
  ~Buffer();

  const BufferType* type() const { return _type; }
  BufferPtr data() { return _data; }
  uint32_t size() const { return _size; }

  Status allocate(uint32_t frame_size);

  Status clear();
  Status mix(const Buffer* other);
  Status mul(float factor);

 private:
  const BufferType* _type;

  uint32_t _frame_size;
  BufferPtr _data;
  uint32_t _size;

  void _free_data();
};

}  // namespace noisicaa

#endif
