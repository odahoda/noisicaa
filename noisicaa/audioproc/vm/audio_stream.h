// -*- mode: c++ -*-

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

#ifndef _NOISICAA_AUDIOPROC_VM_AUDIO_STREAM_H
#define _NOISICAA_AUDIOPROC_VM_AUDIO_STREAM_H

#include <stdint.h>
#include "noisicaa/core/logging.h"
#include "noisicaa/core/status.h"

namespace noisicaa {

using namespace std;

class AudioStreamBase {
public:
  AudioStreamBase(const char* logger_name, const string& address);
  virtual ~AudioStreamBase();

  virtual Status setup();
  virtual void cleanup();

  string address() const { return _address; }

  void close();
  StatusOr<string> receive_bytes();

  Status send_bytes(const char* data, size_t size);
  Status send_bytes(const string& bytes) {
    return send_bytes(bytes.c_str(), bytes.size());
  }

protected:
  static const uint32_t BLOCK_START = 0x2f94727a;
  static const uint32_t CLOSE = 0x3a948d75;

  Status pipe_read(char* data, size_t size);
  Status pipe_write(const char* data, size_t size);

  Logger* _logger;
  string _address;
  int _pipe_in = -1;
  int _pipe_out = -1;

private:
  bool _closed = false;
};

class AudioStreamServer : public AudioStreamBase {
public:
  AudioStreamServer(const string& address);

  Status setup() override;
  void cleanup() override;
};

class AudioStreamClient : public AudioStreamBase {
public:
  AudioStreamClient(const string& address);

  Status setup() override;
  void cleanup() override;
};

}  // namespace noisicaa

#endif
