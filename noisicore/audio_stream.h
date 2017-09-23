// -*- mode: c++ -*-

#ifndef _NOISICORE_AUDIO_STREAM_H
#define _NOISICORE_AUDIO_STREAM_H

#include <stdint.h>
#include <capnp/message.h>
#include <capnp/serialize.h>
#include "noisicaa/core/logging.h"
#include "noisicaa/core/status.h"
#include "noisicore/block_data.capnp.h"

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
  capnp::BlockData::Builder block_data_builder();
  Status send_block(const capnp::BlockData::Builder& builder);

protected:
  Logger* _logger;
  string _address;
  int _pipe_in = -1;
  int _pipe_out = -1;

private:
  Status fill_buffer();
  StatusOr<string> get_line();
  StatusOr<string> get_bytes(size_t num_bytes);

  bool _closed = false;
  string _buffer;
  ::capnp::MallocMessageBuilder _message_builder;
  string _in_message;
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
