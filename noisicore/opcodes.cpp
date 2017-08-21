#include "opcodes.h"

#include "vm.h"
#include "misc.h"

namespace noisicaa {

Status run_END(ProgramState* state, const vector<OpArg>& args) {
  state->end = true;
  return Status::Ok();
}

Status run_COPY(ProgramState* state, const vector<OpArg>& args) {
  int idx1 = args[0].int_value();
  int idx2 = args[1].int_value();
  Buffer* buf1 = state->program->buffers[idx1].get();
  Buffer* buf2 = state->program->buffers[idx2].get();
  assert(buf1->size() == buf2->size());
  memmove(buf2->data(), buf1->data(), buf2->size());
  return Status::Ok();
}

Status run_CLEAR(ProgramState* state, const vector<OpArg>& args) {
  int idx = args[0].int_value();
  Buffer* buf = state->program->buffers[idx].get();
  buf->clear();
  return Status::Ok();
}

Status run_MIX(ProgramState* state, const vector<OpArg>& args) {
  int idx1 = args[0].int_value();
  int idx2 = args[1].int_value();
  Buffer* buf1 = state->program->buffers[idx1].get();
  Buffer* buf2 = state->program->buffers[idx2].get();
  buf2->mix(buf1);
  return Status::Ok();
}

Status run_MUL(ProgramState* state, const vector<OpArg>& args) {
    //     cdef buffers.Buffer buf = self.__buffers[buf_idx]
    //     assert isinstance(buf.type, buffers.FloatArray), str(buf.type)
    //     cdef float* view = <float*>buf.data
    //     for i in range(buf.type.size):
    //         view[i] *= factor
  return Status::Error("Not implemented yet.");
}

Status run_SET_FLOAT(ProgramState* state, const vector<OpArg>& args) {
    // def op_SET_FLOAT(self, ctxt, state, *, buf_idx, value):
    //     cdef buffers.Buffer buf = self.__buffers[buf_idx]
    //     assert isinstance(buf.type, buffers.Float), str(buf.type)
    //     cdef float* data = <float*>buf.data
    //     data[0] = value
  return Status::Error("Not implemented yet.");
}

Status run_OUTPUT(ProgramState* state, const vector<OpArg>& args) {
    // def op_OUTPUT(self, ctxt, state, *, buf_idx, channel):
    //     cdef buffers.Buffer buf = self.__buffers[buf_idx]
    //     assert isinstance(buf.type, buffers.FloatArray), str(buf.type)
    //     assert buf.type.size == ctxt.duration
    //     self.__backend.output(channel, buf.to_bytes())
  return Status::Error("Not implemented yet.");
}

Status run_FETCH_ENTITY(ProgramState* state, const vector<OpArg>& args) {
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

Status run_FETCH_MESSAGES(ProgramState* state, const vector<OpArg>& args) {
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

Status run_FETCH_PARAMETER(ProgramState* state, const vector<OpArg>& args) {
    // def op_FETCH_PARAMETER(self, ctxt, state, *, parameter_idx, buf_idx):
    //     #parameter_name = self.__parameters[parameter_idx]
    //     cdef buffers.Buffer buf = self.__buffers[buf_idx]
    //     buf.clear()
  return Status::Error("Not implemented yet.");
}

Status run_NOISE(ProgramState* state, const vector<OpArg>& args) {
    // def op_NOISE(self, ctxt, state, *, buf_idx):
    //     cdef buffers.Buffer buf = self.__buffers[buf_idx]
    //     assert isinstance(buf.type, buffers.FloatArray), str(buf.type)

    //     cdef float* view = <float*>buf.data
    //     for i in range(buf.type.size):
    //         view[i] = 2 * random.random() - 1.0
  return Status::Error("Not implemented yet.");
}

Status run_SINE(ProgramState* state, const vector<OpArg>& args) {
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

Status init_CONNECT_PORT(ProgramState* state, const vector<OpArg>& args) {
    // def op_CONNECT_PORT(self, ctxt, state, *, node_idx, port_name, buf_idx):
    //     node_id = self.__spec.nodes[node_idx]
    //     cdef node.CustomNode n = self.__graph.find_node(node_id)
    //     cdef buffers.Buffer buf = self.__buffers[buf_idx]
    //     n.connect_port(port_name, buf)
  return Status::Error("Not implemented yet.");
}

Status run_CALL(ProgramState* state, const vector<OpArg>& args) {
    // def op_CALL(self, ctxt, state, *, node_idx):
    //     node_id = self.__spec.nodes[node_idx]
    //     cdef node.CustomNode n = self.__graph.find_node(node_id)
    //     n.run(ctxt)
  return Status::Error("Not implemented yet.");
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
  { OpCode::CONNECT_PORT, "isb", init_CONNECT_PORT, nullptr },
  { OpCode::CALL, "i", nullptr, run_CALL },
};

}  // namespace noisicaa
