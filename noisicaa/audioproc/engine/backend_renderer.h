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

#ifndef _NOISICAA_AUDIOPROC_ENGINE_BACKEND_RENDERER_H
#define _NOISICAA_AUDIOPROC_ENGINE_BACKEND_RENDERER_H

#include <stdlib.h>
#include <memory>
#include <string>
#include "noisicaa/audioproc/engine/backend.h"
#include "noisicaa/audioproc/engine/buffers.h"

namespace noisicaa {

class Realm;

class RendererBackend : public Backend {
public:
  RendererBackend(
      HostSystem* host_system, const pb::BackendSettings& settings,
      void (*callback)(void*, const string&), void* userdata);
  ~RendererBackend() override;

  Status setup(Realm* realm) override;
  void cleanup() override;

  Status begin_block(BlockContext* ctxt) override;
  Status end_block(BlockContext* ctxt) override;
  Status output(BlockContext* ctxt, Channel channel, BufferPtr buffer) override;

 private:
  unique_ptr<BufferData> _samples[2];
  bool _channel_written[2];

  int _datastream = -1;
  size_t _total_samples_written = 0;
  unique_ptr<float> _outbuf;
};

}  // namespace noisicaa

#endif
