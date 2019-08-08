// -*- mode: c++ -*-

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

#ifndef _NOISICAA_AUDIOPROC_ENGINE_PLAYER_H
#define _NOISICAA_AUDIOPROC_ENGINE_PLAYER_H

#include <string>

#include "noisicaa/core/status.h"
#include "noisicaa/core/fifo_queue.h"
#include "noisicaa/audioproc/public/musical_time.h"
#include "noisicaa/audioproc/public/time_mapper.h"

namespace noisicaa {

using namespace std;

class HostSystem;
class Logger;
class BlockContext;

class PlayerStateMutation {
public:
  bool set_playing = false;
  bool playing;

  bool set_current_time = false;
  MusicalTime current_time;

  bool set_loop_enabled = false;
  bool loop_enabled;

  bool set_loop_start_time = false;
  MusicalTime loop_start_time;

  bool set_loop_end_time = false;
  MusicalTime loop_end_time;

  string to_string() const;
};

class PlayerState {
public:
  bool playing = false;
  MusicalTime current_time = MusicalTime(0, 1);
  bool loop_enabled = false;
  MusicalTime loop_start_time = MusicalTime(-1, 1);
  MusicalTime loop_end_time = MusicalTime(-1, 1);
};

class Player {
public:
  Player(const string& realm_name, HostSystem* host_system);

  void update_state(const string& state_serialized);

  void fill_time_map(TimeMapper* time_mapper, BlockContext* ctxt);

private:
  Logger* _logger;
  const string _realm_name;
  HostSystem* _host_system;

  TimeMapper::iterator _tmap_it;

  PlayerState _state;
  FifoQueue<PlayerStateMutation, 128> _mutation_queue;
};

}  // namespace noisicaa

#endif
