// -*- mode: c++ -*-

/*
 * @begin:license
 *
 * Copyright (c) 2015-2017, Benjamin Niemann <pink@odahoda.de>
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

#include "noisicaa/core/logging.h"
#include "noisicaa/audioproc/vm/double_buffered_state_manager.h"
#include "noisicaa/audioproc/vm/processor.h"

namespace noisicaa {

template<class Mutation>
ManagedState<Mutation>::~ManagedState() {}

template<class State, class Mutation>
DoubleBufferedStateManager<State, Mutation>::DoubleBufferedStateManager(Logger* logger)
  : _logger(logger),
    _new_state(nullptr),
    _current_state(new State()),
    _old_state(new State()) {}

template<class State, class Mutation>
DoubleBufferedStateManager<State, Mutation>::DoubleBufferedStateManager(
    State* a, State* b, Logger* logger)
  : _logger(logger),
    _new_state(nullptr),
    _current_state(a),
    _old_state(b) {}

template<class State, class Mutation>
DoubleBufferedStateManager<State, Mutation>::~DoubleBufferedStateManager() {
  State* state = _new_state.exchange(nullptr);
  if (state != nullptr) {
    delete state;
  }
  state = _current_state.exchange(nullptr);
  if (state != nullptr) {
    delete state;
  }
  state = _old_state.exchange(nullptr);
  if (state != nullptr) {
    delete state;
  }
}

template<class State, class Mutation>
void DoubleBufferedStateManager<State, Mutation>::handle_mutation(Mutation* mutation) {
  // Get state instance that we can modify. Either the new state, which hasn't been
  // picked up by the audio thread, or the old state, which can be recycled.
  State* state = _new_state.exchange(nullptr);
  while (state == nullptr) {
    state = _old_state.exchange(nullptr);
  }

  // If the state is behind the latest state (i.e. _latest_seqeuence_number), replay the
  // buffered mutations.
  // Since there are only two state instances and one is always up-to-date (relative to the
  // buffered state), the mutations are not needed after being replayed once and can be
  // discarded.
  if (state->sequence_number < _latest_sequence_number) {
    assert(_latest_sequence_number - state->sequence_number == _buffered_mutations.size());
    for (const auto& it : _buffered_mutations) {
      //_logger->info("Replay %s", it->to_string().c_str());
      state->apply_mutation(it.get());
      ++state->sequence_number;
    }
    _buffered_mutations.clear();
  }

  //_logger->info("Apply %s", mutation->to_string().c_str());
  state->apply_mutation(mutation);
  ++state->sequence_number;

  // Buffer this mutation, so it can be replayed on the other state (which is now at least
  // one mutation behind).
  _buffered_mutations.emplace_back(mutation);
  ++_latest_sequence_number;

  // Make the modified state the new one. It will either be picked up by the audio thread
  // and moved to the current pointer, or another handle_mutation call will apply another change
  // (whichever comes first).
  state = _new_state.exchange(state);
  assert(state == nullptr);
}

template<class State, class Mutation>
State* DoubleBufferedStateManager<State, Mutation>::get_current() {
  // If there is a new state, make it the current. The current state becomes
  // the old state, which will eventually be reused in the main thread.
  // It must not happen that a new program is available, before an old one has
  // been recycled.
  if (_old_state.load() == nullptr) {
    State* state = _new_state.exchange(nullptr);
    if (state != nullptr) {
      State* old_state = _current_state.exchange(state);
      if (old_state) {
        old_state = _old_state.exchange(old_state);
        assert(old_state == nullptr);
      }
    }
  }

  State* state = _current_state.load();
  assert(state != nullptr);
  return state;
}

}
