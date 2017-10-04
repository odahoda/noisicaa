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

#ifndef _NOISICAA_AUDIOPROC_VM_OPCODES_H
#define _NOISICAA_AUDIOPROC_VM_OPCODES_H

#include <string>
#include <vector>
#include <stdint.h>
#include "noisicaa/core/status.h"
#include "noisicaa/audioproc/vm/block_context.h"

namespace noisicaa {

using namespace std;

class ProgramState;

enum OpCode {
  // control flow
  NOOP = 0,
  END,

  // buffer access
  COPY,
  CLEAR,
  MIX,
  MUL,
  SET_FLOAT,

  // I/O
  OUTPUT,
  FETCH_BUFFER,
  FETCH_MESSAGES,
  FETCH_CONTROL_VALUE,

  // generators
  NOISE,
  SINE,
  MIDI_MONKEY,

  // processors
  CONNECT_PORT,
  CALL,

  // misc
  LOG_RMS,
  LOG_ATOM,

  NUM_OPCODES,
};

enum OpArgType {
  INT = 0,
  FLOAT,
  STRING,
};

class OpArg {
public:
  OpArg(int64_t value) : _type(OpArgType::INT), _int_value(value) {}
  OpArg(float value) : _type(OpArgType::FLOAT), _float_value(value) {}
  OpArg(const string& value) : _type(OpArgType::STRING), _string_value(value) {}

  OpArgType type() const { return _type; }

  int64_t int_value() const { return _int_value; }
  float float_value() const { return _float_value; }
  const string& string_value() const { return _string_value; }

private:
  OpArgType _type;
  int64_t _int_value;
  float _float_value;
  string _string_value;
};

typedef Status (*OpFunc)(
    BlockContext* ctxt, ProgramState* state, const vector<OpArg>& args);

struct OpSpec {
  OpCode opcode;
  const char* name;
  const char* argspec;
  OpFunc init;
  OpFunc run;
};

extern struct OpSpec opspecs[NUM_OPCODES];

}  // namespace noisicaa

#endif
