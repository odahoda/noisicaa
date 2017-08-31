// -*- mode: c++ -*-

#ifndef _NOISICORE_AUDIO_STREAM_H
#define _NOISICORE_AUDIO_STREAM_H

#include "status.h"

namespace noisicaa {

using namespace std;

class AudioStreamBase {
public:
  AudioStreamBase(const string& address);
  virtual ~AudioStreamBase();

  virtual Status setup();
  virtual void cleanup();

  string address() const { return _address; }

  void close();
  StatusOr<string> receive_frame_bytes();
  StatusOr<string> receive_frame();
  Status send_frame_bytes(const string& frame_bytes);
  Status send_frame(const string& frame);

protected:
  string _address;
  int _pipe_in = -1;
  int _pipe_out = -1;

private:
  Status fill_buffer();
  StatusOr<string> get_line();
  StatusOr<string> get_bytes(size_t num_bytes);

  bool _closed = false;
  string _buffer;
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
