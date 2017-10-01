// -*- mode: c++ -*-

#ifndef _NOISICAA_AUDIOPROC_VM_BACKEND_H
#define _NOISICAA_AUDIOPROC_VM_BACKEND_H

#include <mutex>
#include <string>
#include <vector>
#include "noisicaa/core/logging.h"
#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/vm/buffers.h"

namespace noisicaa {

using namespace std;

class BlockContext;
class VM;

struct BackendSettings {
  string ipc_address;

  uint32_t block_size;
};

class Backend {
public:
  virtual ~Backend();

  static StatusOr<Backend*> create(const string& name, const BackendSettings& settings);

  virtual Status setup(VM* vm);
  virtual void cleanup();

  Status send_message(const string& msg);

  virtual Status begin_block(BlockContext* ctxt) = 0;
  virtual Status end_block(BlockContext* ctxt) = 0;
  virtual Status output(BlockContext* ctxt, const string& channel, BufferPtr samples) = 0;

  void stop() { _stopped = true; }
  bool stopped() const { return _stopped; }

protected:
  Backend(const char* logger_name, const BackendSettings& settings);

  Logger* _logger;
  BackendSettings _settings;
  VM* _vm = nullptr;
  bool _stopped = false;

  mutex _msg_queue_mutex;
  vector<string> _msg_queue;
};

}  // namespace noisicaa

#endif
