#include <assert.h>
#include <string.h>
#include "noisicaa/core/logging.h"
#include "noisicaa/audioproc/vm/host_system_csound.h"

namespace noisicaa {

CSoundSubSystem::CSoundSubSystem()
  : _logger(LoggerRegistry::get_logger("noisicaa.audioproc.vm.csound")) {}

CSoundSubSystem::~CSoundSubSystem() {
  cleanup();
}

CSoundSubSystem* CSoundSubSystem::_instance = nullptr;

Status CSoundSubSystem::setup() {
  if (_instance == nullptr) {
    _instance = this;
    memset(_log_buf, 0, sizeof(_log_buf));
    csoundSetDefaultMessageCallback(_log_cb);
    _log_cb_installed = true;
  }
  return Status::Ok();
}

void CSoundSubSystem::cleanup() {
  if (_log_cb_installed) {
    csoundSetDefaultMessageCallback(nullptr);
    _instance = nullptr;
    _log_cb_installed = false;
  }
}

void CSoundSubSystem::_log_cb(CSOUND* csnd, int attr, const char* fmt, va_list args) {
  assert(_instance != nullptr);
  _instance->_log_cb(attr, fmt, args);
}

void CSoundSubSystem::_log_cb(int attr, const char* fmt, va_list args) {
  LogLevel level;
  switch (attr & CSOUNDMSG_TYPE_MASK) {
  case CSOUNDMSG_ORCH:
  case CSOUNDMSG_REALTIME:
  case CSOUNDMSG_DEFAULT:
    // Global (not tied to a csound instance) csound messages are not that interesting.
    // Use DEBUG level instead of INFO.
    level = LogLevel::DEBUG;
    break;
  case CSOUNDMSG_WARNING:
    level = LogLevel::WARNING;
    break;
  case CSOUNDMSG_ERROR:
    level = LogLevel::ERROR;
    break;
  }

  size_t bytes_used = strlen(_log_buf);
  vsnprintf(_log_buf + bytes_used, sizeof(_log_buf) - bytes_used, fmt, args);

  while (_log_buf[0]) {
    char *eol = strchr(_log_buf, '\n');
    if (eol == nullptr) {
      break;
    }

    *eol = 0;
    _logger->log(level, "%s", _log_buf);

    memmove(_log_buf, eol + 1, strlen(eol + 1) + 1);
  }
}

}  // namespace noisicaa
