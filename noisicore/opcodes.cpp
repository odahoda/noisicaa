#include "opcodes.h"

namespace noisicaa {

struct OpSpec opspecs[NUM_OPCODES] = {
  // control flow
  { OpCode::NOOP, "" },
  { OpCode::END, "" },

  // buffer access
  { OpCode::COPY, "bb" },
  { OpCode::CLEAR, "b" },
  { OpCode::MIX, "bb" },
  { OpCode::MUL, "bf" },
  { OpCode::SET_FLOAT, "bf" },

  // I/O
  { OpCode::OUTPUT, "bs" },
  { OpCode::FETCH_ENTITY, "sb" },
  { OpCode::FETCH_MESSAGES, "ib" },
  { OpCode::FETCH_PARAMETER, "sb" },

  // generators
  { OpCode::NOISE, "b" },
  { OpCode::SINE, "bf" },

  // processors
  { OpCode::CONNECT_PORT, "isb" },
  { OpCode::CALL, "i" },
};

    // @at_performance
    // def op_COPY_BUFFER(self, ctxt, state, *, src_idx, dest_idx):
    //     cdef buffers.Buffer src = self.__buffers[src_idx]
    //     cdef buffers.Buffer dest = self.__buffers[dest_idx]
    //     assert len(src.type) == len(dest.type)
    //     string.memmove(dest.data, src.data, len(dest.type))

    // @at_performance
    // def op_CLEAR_BUFFER(self, ctxt, state, *, buf_idx):
    //     cdef buffers.Buffer buf = self.__buffers[buf_idx]
    //     buf.clear()

    // @at_performance
    // def op_SET_FLOAT(self, ctxt, state, *, buf_idx, value):
    //     cdef buffers.Buffer buf = self.__buffers[buf_idx]
    //     assert isinstance(buf.type, buffers.Float), str(buf.type)
    //     cdef float* data = <float*>buf.data
    //     data[0] = value

    // @at_performance
    // def op_OUTPUT(self, ctxt, state, *, buf_idx, channel):
    //     cdef buffers.Buffer buf = self.__buffers[buf_idx]
    //     assert isinstance(buf.type, buffers.FloatArray), str(buf.type)
    //     assert buf.type.size == ctxt.duration
    //     self.__backend.output(channel, buf.to_bytes())

    // @at_performance
    // def op_FETCH_ENTITY(self, ctxt, state, *, entity_id, buf_idx):
    //     cdef buffers.Buffer buf = self.__buffers[buf_idx]
    //     try:
    //         entity = ctxt.entities[entity_id]
    //     except KeyError:
    //         buf.clear()
    //     else:
    //         buf.set_bytes(entity.data)

    // @at_performance
    // def op_FETCH_PARAMETER(self, ctxt, state, *, parameter_idx, buf_idx):
    //     #parameter_name = self.__parameters[parameter_idx]
    //     cdef buffers.Buffer buf = self.__buffers[buf_idx]
    //     buf.clear()

    // @at_performance
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

    // @at_performance
    // def op_NOISE(self, ctxt, state, *, buf_idx):
    //     cdef buffers.Buffer buf = self.__buffers[buf_idx]
    //     assert isinstance(buf.type, buffers.FloatArray), str(buf.type)

    //     cdef float* view = <float*>buf.data
    //     for i in range(buf.type.size):
    //         view[i] = 2 * random.random() - 1.0

    // @at_performance
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

    // @at_performance
    // def op_MUL(self, ctxt, state, *, buf_idx, factor):
    //     cdef buffers.Buffer buf = self.__buffers[buf_idx]
    //     assert isinstance(buf.type, buffers.FloatArray), str(buf.type)
    //     cdef float* view = <float*>buf.data
    //     for i in range(buf.type.size):
    //         view[i] *= factor

    // @at_performance
    // def op_MIX(self, ctxt, state, *, src_idx, dest_idx):
    //     self.__buffers[dest_idx].mix(self.__buffers[src_idx])

    // @at_init
    // def op_CONNECT_PORT(self, ctxt, state, *, node_idx, port_name, buf_idx):
    //     node_id = self.__spec.nodes[node_idx]
    //     cdef node.CustomNode n = self.__graph.find_node(node_id)
    //     cdef buffers.Buffer buf = self.__buffers[buf_idx]
    //     n.connect_port(port_name, buf)

    // @at_performance
    // def op_CALL(self, ctxt, state, *, node_idx):
    //     node_id = self.__spec.nodes[node_idx]
    //     cdef node.CustomNode n = self.__graph.find_node(node_id)
    //     n.run(ctxt)

}  // namespace noisicaa
