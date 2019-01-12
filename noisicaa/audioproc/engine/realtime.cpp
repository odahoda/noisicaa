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

#include <sched.h>
#include <sys/resource.h>

#include "noisicaa/audioproc/engine/realtime.h"

namespace noisicaa {

Status set_thread_to_rt_priority(Logger* logger) {
  struct rlimit limits;
  if (getrlimit(RLIMIT_RTPRIO, &limits) < 0) {
    return OSERROR_STATUS("getrlimit(RLIMIT_RTPRIO) failed");
  }

  rlim_t max_rt_prio = limits.rlim_max;
  logger->info("Max RT priority: %d", max_rt_prio);
  if (max_rt_prio == 0) {
    logger->warning(
        "Realtime scheduling not available. See e.g. http://jackaudio.org/faq/linux_rt_config.html"
        " for instructions to enabled it.");
  } else {
    struct sched_param params;
    params.sched_priority = max_rt_prio;
    if (sched_setscheduler(0, SCHED_FIFO, &params) < 0) {
      return OSERROR_STATUS(
          "sched_setscheduler(0, SCHED_FIFO, {sched_priority=%d}) failed", max_rt_prio);
    }

    logger->info("Using realtime priority %d for audio thread.", max_rt_prio);
  }
  return Status::Ok();
}

}  // namespace noisicaa
