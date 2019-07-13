// -*- mode: c++ -*-

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

#ifndef _NOISICAA_AUDIOPROC_ENGINE_BUFFERS_H
#define _NOISICAA_AUDIOPROC_ENGINE_BUFFERS_H

#include <memory>
#include <stdint.h>
#include "lv2/lv2plug.in/ns/ext/atom/forge.h"
#include "lv2/lv2plug.in/ns/ext/urid/urid.h"
#include "noisicaa/core/status.h"
#include "noisicaa/node_db/node_description.pb.h"

namespace noisicaa {

using namespace std;

class HostSystem;

typedef uint8_t BufferData;
typedef BufferData* BufferPtr;

class BufferType {
public:
  virtual ~BufferType();

  virtual uint32_t size(HostSystem* host_system) const = 0;
  pb::PortDescription::Type type() const {
    return _type;
  }

  virtual Status setup(HostSystem* host_system, BufferPtr buf) const;
  virtual void cleanup(HostSystem* host_system, BufferPtr buf) const;

  virtual Status clear_buffer(HostSystem* host_system, BufferPtr buf) const = 0;
  virtual Status mix_buffers(HostSystem* host_system, const BufferPtr buf1, BufferPtr buf2) const = 0;
  virtual Status mul_buffer(HostSystem* host_system, BufferPtr buf, float factor) const = 0;

protected:
  BufferType(pb::PortDescription::Type type);

private:
  pb::PortDescription::Type _type;
};

class FloatControlValueBuffer : public BufferType {
public:
  struct ControlValue {
    float value;
    uint32_t generation;
  };

  FloatControlValueBuffer();

  uint32_t size(HostSystem* host_system) const override;

  Status clear_buffer(HostSystem* host_system, BufferPtr buf) const override;
  Status mix_buffers(HostSystem* host_system, const BufferPtr buf1, BufferPtr buf2) const override;
  Status mul_buffer(HostSystem* host_system, BufferPtr buf, float factor) const override;
};

class FloatAudioBlockBuffer : public BufferType {
public:
  FloatAudioBlockBuffer(pb::PortDescription::Type type);

  uint32_t size(HostSystem* host_system) const override;

  Status clear_buffer(HostSystem* host_system, BufferPtr buf) const override;
  Status mix_buffers(HostSystem* host_system, const BufferPtr buf1, BufferPtr buf2) const override;
  Status mul_buffer(HostSystem* host_system, BufferPtr buf, float factor) const override;
};

class AtomDataBuffer : public BufferType {
public:
  AtomDataBuffer();

  uint32_t size(HostSystem* host_system) const override;

  Status clear_buffer(HostSystem* host_system, BufferPtr buf) const override;
  Status mix_buffers(HostSystem* host_system, const BufferPtr buf1, BufferPtr buf2) const override;
  Status mul_buffer(HostSystem* host_system, BufferPtr buf, float factor) const override;
};

class PluginCondBuffer : public BufferType {
public:
  PluginCondBuffer();

  uint32_t size(HostSystem* host_system) const override;

  Status setup(HostSystem* host_system, BufferPtr buf) const override;
  void cleanup(HostSystem* host_system, BufferPtr buf) const override;

  Status clear_buffer(HostSystem* host_system, BufferPtr buf) const override;
  Status mix_buffers(HostSystem* host_system, const BufferPtr buf1, BufferPtr buf2) const override;
  Status mul_buffer(HostSystem* host_system, BufferPtr buf, float factor) const override;

  Status set_cond(BufferPtr buf);
  Status clear_cond(BufferPtr buf);
  Status wait_cond(BufferPtr buf);
};

class Buffer {
public:
  Buffer(HostSystem* host_system, const BufferType* type, BufferPtr data);
  ~Buffer();

  const BufferType* type() const { return _type; }
  uint32_t size() const { return _type->size(_host_system); }

  BufferPtr data() { return _data; }

  Status setup();
  void cleanup();

  Status clear();
  Status mix(const Buffer* other);
  Status mul(float factor);

private:
  const BufferType* _type;
  HostSystem* _host_system;
  BufferPtr _data;
};

}  // namespace noisicaa

#endif
