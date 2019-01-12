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

#include <assert.h>
#include <string.h>
#include "noisicaa/core/logging.h"
#include "noisicaa/host_system/host_system_csound.h"

namespace noisicaa {

CSoundSubSystem::CSoundSubSystem()
  : _logger(LoggerRegistry::get_logger("noisicaa.host_system.csound")) {}

CSoundSubSystem::~CSoundSubSystem() {
  cleanup();
}

CSoundSubSystem* CSoundSubSystem::_instance = nullptr;

Status CSoundSubSystem::setup() {
  csoundInitialize(CSOUNDINIT_NO_SIGNAL_HANDLER | CSOUNDINIT_NO_ATEXIT);

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
  LogLevel level = LogLevel::INFO;
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
