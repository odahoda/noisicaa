#include "opcodes.h"

#include "backend.h"
#include "vm.h"
#include "misc.h"

namespace noisicaa {

Status run_END(BlockContext* ctxt, ProgramState* state, const vector<OpArg>& args) {
  state->end = true;
  return Status::Ok();
}

Status run_COPY(BlockContext* ctxt, ProgramState* state, const vector<OpArg>& args) {
  int idx1 = args[0].int_value();
  int idx2 = args[1].int_value();
  Buffer* buf1 = state->program->buffers[idx1].get();
  Buffer* buf2 = state->program->buffers[idx2].get();
  assert(buf1->size() == buf2->size());
  memmove(buf2->data(), buf1->data(), buf2->size());
  return Status::Ok();
}

Status run_CLEAR(BlockContext* ctxt, ProgramState* state, const vector<OpArg>& args) {
  int idx = args[0].int_value();
  Buffer* buf = state->program->buffers[idx].get();
  buf->clear();
  return Status::Ok();
}

Status run_MIX(BlockContext* ctxt, ProgramState* state, const vector<OpArg>& args) {
  int idx1 = args[0].int_value();
  int idx2 = args[1].int_value();
  Buffer* buf1 = state->program->buffers[idx1].get();
  Buffer* buf2 = state->program->buffers[idx2].get();
  buf2->mix(buf1);
  return Status::Ok();
}

Status run_MUL(BlockContext* ctxt, ProgramState* state, const vector<OpArg>& args) {
  int idx = args[0].int_value();
  float factor = args[1].float_value();
  Buffer* buf = state->program->buffers[idx].get();
  buf->mul(factor);
  return Status::Ok();
}

Status run_SET_FLOAT(BlockContext* ctxt, ProgramState* state, const vector<OpArg>& args) {
    // def op_SET_FLOAT(self, ctxt, state, *, buf_idx, value):
    //     cdef buffers.Buffer buf = self.__buffers[buf_idx]
    //     assert isinstance(buf.type, buffers.Float), str(buf.type)
    //     cdef float* data = <float*>buf.data
    //     data[0] = value
  return Status::Error("Not implemented yet.");
}

Status run_OUTPUT(BlockContext* ctxt, ProgramState* state, const vector<OpArg>& args) {
  int idx = args[0].int_value();
  string channel = args[1].string_value();
  Buffer* buf = state->program->buffers[idx].get();

  return state->backend->output(channel, buf->data());
}

Status run_FETCH_ENTITY(BlockContext* ctxt, ProgramState* state, const vector<OpArg>& args) {
    // def op_FETCH_ENTITY(self, ctxt, state, *, entity_id, buf_idx):
    //     cdef buffers.Buffer buf = self.__buffers[buf_idx]
    //     try:
    //         entity = ctxt.entities[entity_id]
    //     except KeyError:
    //         buf.clear()
    //     else:
    //         buf.set_bytes(entity.data)
  return Status::Error("Not implemented yet.");
}

Status run_FETCH_MESSAGES(BlockContext* ctxt, ProgramState* state, const vector<OpArg>& args) {
    // def op_FETCH_MESSAGES(self, ctxt, state, *, labelset, buf_idx):
    //     cdef buffers.Buffer buf = self.__buffers[buf_idx]

    //     forge = lv2.AtomForge(lv2.static_mapper)
    //     forge.set_buffer(buf.data, len(buf.type))

    //     with forge.sequence():
    //         for msg in ctxt.messages:
    //             if msg.type != core.MessageType.atom:
    //                 continue

    //             matched = all(
    //                 any(label_b.key == label_a.key and label_b.value == label_a.value
    //                     for label_b in msg.labelset.labels)
    //                 for label_a in labelset.labels)

    //             if not matched:
    //                 continue

    //             forge.write_raw_event(0, msg.data, len(msg.data))

    //     # TODO: clear remainder of buf.
  return Status::Error("Not implemented yet.");
}

Status run_FETCH_PARAMETER(BlockContext* ctxt, ProgramState* state, const vector<OpArg>& args) {
    // def op_FETCH_PARAMETER(self, ctxt, state, *, parameter_idx, buf_idx):
    //     #parameter_name = self.__parameters[parameter_idx]
    //     cdef buffers.Buffer buf = self.__buffers[buf_idx]
    //     buf.clear()
  return Status::Error("Not implemented yet.");
}

Status run_NOISE(BlockContext* ctxt, ProgramState* state, const vector<OpArg>& args) {
  int idx = args[0].int_value();
  Buffer* buf = state->program->buffers[idx].get();

  float* data = (float*)buf->data();
  for (uint32_t i = 0 ; i < ctxt->block_size ; ++i) {
    *data++ = 2.0 * drand48() - 1.0;
  }
  return Status::Ok();
}

Status run_SINE(BlockContext* ctxt, ProgramState* state, const vector<OpArg>& args) {
    // def op_SINE(self, ctxt, state, *, buf_idx, freq):
    //     cdef buffers.Buffer buf = self.__buffers[buf_idx]
    //     assert isinstance(buf.type, buffers.FloatArray), str(buf.type)
    //     cdef float* view = <float*>buf.data

    //     p = state.get('p', 0.0)
    //     for i in range(buf.type.size):
    //         view[i] = math.sin(p)
    //         p += 2 * math.pi * freq / self.__sample_rate
    //         if p > 2 * math.pi:
    //             p -= 2 * math.pi
    //     state['p'] = p
  return Status::Error("Not implemented yet.");
}

Status init_CONNECT_PORT(BlockContext* ctxt, ProgramState* state, const vector<OpArg>& args) {
  int processor_idx = args[0].int_value();
  int port_idx = args[1].int_value();
  int buf_idx = args[2].int_value();
  Processor* processor = state->program->spec->get_processor(processor_idx);
  Buffer* buf = state->program->buffers[buf_idx].get();

  processor->connect_port(port_idx, buf->data());
  return Status::Ok();
}

Status run_CALL(BlockContext* ctxt, ProgramState* state, const vector<OpArg>& args) {
  int processor_idx = args[0].int_value();
  Processor* processor = state->program->spec->get_processor(processor_idx);

  processor->run(ctxt);
  return Status::Ok();
}

struct OpSpec opspecs[NUM_OPCODES] = {
  // control flow
  { OpCode::NOOP, "", nullptr, nullptr },
  { OpCode::END, "", nullptr, run_END },

  // buffer access
  { OpCode::COPY, "bb", nullptr, run_COPY },
  { OpCode::CLEAR, "b", nullptr, run_CLEAR },
  { OpCode::MIX, "bb", nullptr, run_MIX },
  { OpCode::MUL, "bf", nullptr, run_MUL },
  { OpCode::SET_FLOAT, "bf", nullptr, run_SET_FLOAT },

  // I/O
  { OpCode::OUTPUT, "bs", nullptr, run_OUTPUT },
  { OpCode::FETCH_ENTITY, "sb", nullptr, run_FETCH_ENTITY },
  { OpCode::FETCH_MESSAGES, "ib", nullptr, run_FETCH_MESSAGES },
  { OpCode::FETCH_PARAMETER, "sb", nullptr, run_FETCH_PARAMETER },

  // generators
  { OpCode::NOISE, "b", nullptr, run_NOISE },
  { OpCode::SINE, "bf", nullptr, run_SINE },

  // processors
  { OpCode::CONNECT_PORT, "pib", init_CONNECT_PORT, nullptr },
  { OpCode::CALL, "p", nullptr, run_CALL },
};

}  // namespace noisicaa
