#ifndef _NOISICORE_OPCODES_H
#define _NOISICORE_OPCODES_H

#include <string>
#include <vector>
#include <stdint.h>

#include "status.h"
#include "block_context.h"

using std::string;
using std::vector;

namespace noisicaa {

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
  FETCH_ENTITY,
  FETCH_MESSAGES,
  FETCH_PARAMETER,

  // generators
  NOISE,
  SINE,

  // processors
  CONNECT_PORT,
  CALL,

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
  const char* argspec;
  OpFunc init;
  OpFunc run;
};

extern struct OpSpec opspecs[NUM_OPCODES];

}  // namespace noisicaa

#endif
