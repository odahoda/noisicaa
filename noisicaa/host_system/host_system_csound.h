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

#ifndef _NOISICAA_HOST_SYSTEM_HOST_SYSTEM_CSOUND_H
#define _NOISICAA_HOST_SYSTEM_HOST_SYSTEM_CSOUND_H

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
