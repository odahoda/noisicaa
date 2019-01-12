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

#include <string.h>

#include <gperftools/profiler.h>

#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/engine/profile.h"

namespace {

static thread_local bool profile_thread = false;

int filter_in_thread(void* arg) {
  return profile_thread;
}

}

namespace noisicaa {

void enable_profiling_in_thread() {
  profile_thread = true;
}

Status start_profiler(const string& path) {
  struct ProfilerOptions options;
  memset(&options, 0, sizeof(ProfilerOptions));
  options.filter_in_thread = filter_in_thread;
  if (ProfilerStartWithOptions(path.c_str(), &options) == 0) {
    return ERROR_STATUS("Failed to start profiler");
  }

  return Status::Ok();
}

Status stop_profiler() {
  ProfilerStop();

  return Status::Ok();
}

}  // namespace noisicaa
