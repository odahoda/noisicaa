// -*- mode: c++ -*-

#ifndef _NOISICAA_AUDIOPROC_VM_HOST_SYSTEM_CSOUND_H
#define _NOISICAA_AUDIOPROC_VM_HOST_SYSTEM_CSOUND_H

#include <unordered_map>
#include "csound/csound.h"
#include "noisicaa/core/status.h"

namespace noisicaa {

class Logger;

class CSoundSubSystem {
public:
  CSoundSubSystem();
  ~CSoundSubSystem();

  Status setup();
  void cleanup();

private:
  Logger* _logger;

  static CSoundSubSystem* _instance;
  static void _log_cb(CSOUND* csnd, int attr, const char* fmt, va_list args);
  void _log_cb(int attr, const char* fmt, va_list args);
  char _log_buf[10240];
  bool _log_cb_installed = false;
};

}  // namespace noisicaa

#endif
