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

#ifndef _NOISICAA_AUDIOPROC_VM_DOUBLE_BUFFERED_STATE_MANAGER_H
#define _NOISICAA_AUDIOPROC_VM_DOUBLE_BUFFERED_STATE_MANAGER_H

#include <stdint.h>
#include <atomic>
#include <memory>
#include <vector>

namespace noisicaa {

using namespace std;

class Logger;

template <class Mutation>
class ManagedState {
public:
  virtual ~ManagedState();

  uint64_t sequence_number = 0;

  virtual void apply_mutation(Mutation* mutation) = 0;
};

template <class State, class Mutation>
class DoubleBufferedStateManager {
public:
  DoubleBufferedStateManager(Logger* logger);
  DoubleBufferedStateManager(State* a, State* b, Logger* logger);
  ~DoubleBufferedStateManager();

  void handle_mutation(Mutation* msg);
  State* get_current();

protected:
  Logger* _logger;

private:
  atomic<State*> _new_state;
  atomic<State*> _current_state;
  atomic<State*> _old_state;

  vector<unique_ptr<Mutation>> _buffered_mutations;
  uint64_t _latest_sequence_number = 0;
};

}  // namespace noisicaa

#endif
