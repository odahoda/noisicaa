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

#include <math.h>
#include <stdlib.h>

#include "lv2/lv2plug.in/ns/ext/atom/atom.h"

#include "noisicaa/core/perf_stats.h"
#include "noisicaa/audioproc/engine/opcodes.h"
#include "noisicaa/host_system/host_system.h"
#include "noisicaa/audioproc/engine/spec.h"
#include "noisicaa/audioproc/engine/control_value.h"
#include "noisicaa/audioproc/engine/processor.h"
#include "noisicaa/audioproc/engine/message_queue.h"
#include "noisicaa/audioproc/engine/realm.h"

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
  int idx = args[0].int_value();
  float value = args[1].float_value();
  Buffer* buf = state->program->buffers[idx].get();
  float* data = (float*)buf->data();
  *data = value;
  return Status::Ok();
}

Status run_FETCH_CONTROL_VALUE(BlockContext* ctxt, ProgramState* state, const vector<OpArg>& args) {
  int cv_idx = args[0].int_value();
  int buf_idx = args[1].int_value();
  ControlValue* cv = state->program->spec->get_control_value(cv_idx);
  Buffer* buf = state->program->buffers[buf_idx].get();

  switch (cv->type()) {
  case ControlValueType::FloatCV: {
    FloatControlValue* fcv = (FloatControlValue*)cv;
    FloatControlValueBuffer::ControlValue* data = (FloatControlValueBuffer::ControlValue*)buf->data();
    data->value = fcv->value();
    data->generation = fcv->generation();
    return Status::Ok();
  }
  case ControlValueType::IntCV:
    return ERROR_STATUS("IntControlValue not implemented yet.");
  default:
    return ERROR_STATUS("Invalid ControlValue type %d.", cv->type());
  }
}

Status run_POST_RMS(BlockContext* ctxt, ProgramState* state, const vector<OpArg>& args) {
  const string& node_id = args[0].string_value();
  int port_index = args[1].int_value();
  int idx = args[2].int_value();
  Buffer* buf = state->program->buffers[idx].get();

  float* data = (float*)buf->data();
  float sum = 0.0;
  for (uint32_t i = 0 ; i < state->host_system->block_size() ; ++i) {
    sum += data[i] * data[i];
  }

  float rms = sqrtf(sum / state->host_system->block_size());

  uint8_t atom[200];
  LV2_Atom_Forge forge;
  lv2_atom_forge_init(&forge, &state->host_system->lv2->urid_map);
  lv2_atom_forge_set_buffer(&forge, atom, sizeof(atom));

  LV2_Atom_Forge_Frame oframe;
  lv2_atom_forge_object(&forge, &oframe, state->host_system->lv2->urid.core_nodemsg, 0);

  lv2_atom_forge_key(&forge, state->host_system->lv2->urid.core_portrms);
  LV2_Atom_Forge_Frame tframe;
  lv2_atom_forge_tuple(&forge, &tframe);
  lv2_atom_forge_int(&forge, port_index);
  lv2_atom_forge_float(&forge, rms);
  lv2_atom_forge_pop(&forge, &tframe);

  lv2_atom_forge_pop(&forge, &oframe);

  NodeMessage::push(ctxt->out_messages, node_id, (LV2_Atom*)atom);

  return Status::Ok();
}

Status run_NOISE(BlockContext* ctxt, ProgramState* state, const vector<OpArg>& args) {
  int idx = args[0].int_value();
  Buffer* buf = state->program->buffers[idx].get();

  float* data = (float*)buf->data();
  for (uint32_t i = 0 ; i < state->host_system->block_size() ; ++i) {
    *data++ = 2.0 * drand48() - 1.0;
  }
  return Status::Ok();
}

Status run_MIDI_MONKEY(BlockContext* ctxt, ProgramState* state, const vector<OpArg>& args) {
  int idx = args[0].int_value();
  float prob = args[1].float_value();
  Buffer* buf = state->program->buffers[idx].get();

  LV2_Atom_Forge forge;
  lv2_atom_forge_init(&forge, &state->host_system->lv2->urid_map);

  LV2_Atom_Forge_Frame frame;
  lv2_atom_forge_set_buffer(&forge, buf->data(), buf->size());

  lv2_atom_forge_sequence_head(&forge, &frame, state->host_system->lv2->urid.atom_frame_time);
  if (drand48() < prob) {
    uint8_t msg[3] = { 0x90, 62, 100 };
    lv2_atom_forge_frame_time(&forge, random() % state->host_system->block_size());
    lv2_atom_forge_atom(&forge, 3, state->host_system->lv2->urid.midi_event);
    lv2_atom_forge_write(&forge, msg, 3);
  }
  lv2_atom_forge_pop(&forge, &frame);

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
  return ERROR_STATUS("SINE not implemented yet.");
}

Status init_CONNECT_PORT(BlockContext* ctxt, ProgramState* state, const vector<OpArg>& args) {
  int processor_idx = args[0].int_value();
  int port_idx = args[1].int_value();
  int buf_idx = args[2].int_value();
  Processor* processor = state->program->spec->get_processor(processor_idx);
  Buffer* buf = state->program->buffers[buf_idx].get();
  processor->connect_port(ctxt, port_idx, buf->data());
  return Status::Ok();
}

Status run_CALL(BlockContext* ctxt, ProgramState* state, const vector<OpArg>& args) {
  int processor_idx = args[0].int_value();
  Processor* processor = state->program->spec->get_processor(processor_idx);
  processor->process_block(ctxt, state->program->time_mapper.get());
  return Status::Ok();
}

Status run_LOG_RMS(BlockContext* ctxt, ProgramState* state, const vector<OpArg>& args) {
  int idx = args[0].int_value();
  Buffer* buf = state->program->buffers[idx].get();

  float* data = (float*)buf->data();
  float sum = 0.0;
  for (uint32_t i = 0 ; i < state->host_system->block_size() ; ++i) {
    sum += data[i] * data[i];
  }

  state->logger->info("Block %d, rms=%.3f", idx, sum / state->host_system->block_size());

  return Status::Ok();
}

Status run_LOG_ATOM(BlockContext* ctxt, ProgramState* state, const vector<OpArg>& args) {
  int idx = args[0].int_value();
  Buffer* buf = state->program->buffers[idx].get();

  LV2_Atom_Sequence* seq = (LV2_Atom_Sequence*)buf->data();
  if (seq->atom.type != state->host_system->lv2->urid.atom_sequence) {
    return ERROR_STATUS(
        "Buffer %d: Excepted sequence (%d), got %d.",
        idx, state->host_system->lv2->urid.atom_sequence, seq->atom.type);
  }
  LV2_Atom_Event* event = lv2_atom_sequence_begin(&seq->body);

  while (!lv2_atom_sequence_is_end(&seq->body, seq->atom.size, event)) {
    state->logger->info("Buffer %d, event %d @%d", idx, event->body.type, event->time.frames);
    event = lv2_atom_sequence_next(event);
  }

  return Status::Ok();
}

Status run_CALL_CHILD_REALM(BlockContext* ctxt, ProgramState* state, const vector<OpArg>& args) {
  int realm_idx = args[0].int_value();
  Realm* realm = state->program->spec->get_child_realm(realm_idx);
  int out_left_idx = args[1].int_value();
  Buffer* out_left_buf = state->program->buffers[out_left_idx].get();
  int out_right_idx = args[2].int_value();
  Buffer* out_right_buf = state->program->buffers[out_right_idx].get();

  StatusOr<Program*> stor_program = realm->get_active_program();
  RETURN_IF_ERROR(stor_program);
  Program* program = stor_program.result();
  if (program != nullptr) {
    PerfStats* perf = realm->block_context()->perf.get();
    perf->reset();

    realm->block_context()->out_messages = ctxt->out_messages;
    RETURN_IF_ERROR(realm->process_block(program));
    realm->block_context()->out_messages = nullptr;

    for (int i = 0 ; i < perf->num_spans() ; ++i) {
      PerfStats::Span span = perf->span(i);
      if (span.parent_id == 0) {
        span.parent_id = ctxt->perf->current_span_id();
      }
      ctxt->perf->append_span(span);
    }

    Buffer* child_out_left_buf = realm->get_buffer("sink:in:left");
    if (child_out_left_buf != nullptr) {
      assert(out_left_buf->size() == child_out_left_buf->size());
      memmove(out_left_buf->data(), child_out_left_buf->data(), out_left_buf->size());
    } else {
      state->logger->warning("No sink:in:left buffer in child realm '%s'", realm->name().c_str());
      out_left_buf->clear();
    }

    Buffer* child_out_right_buf = realm->get_buffer("sink:in:right");
    if (child_out_right_buf != nullptr) {
      assert(out_right_buf->size() == child_out_right_buf->size());
      memmove(out_right_buf->data(), child_out_right_buf->data(), out_right_buf->size());
    } else {
      state->logger->warning("No sink:in:right buffer in child realm '%s'", realm->name().c_str());
      out_right_buf->clear();
    }
  } else {
      out_left_buf->clear();
      out_right_buf->clear();
  }
  return Status::Ok();
}

struct OpSpec opspecs[NUM_OPCODES] = {
  // control flow
  { OpCode::NOOP, "NOOP", "", nullptr, nullptr },
  { OpCode::END, "END", "", nullptr, run_END },
  { OpCode::CALL_CHILD_REALM, "CALL_CHILD_REALM", "rbb", nullptr, run_CALL_CHILD_REALM },

  // buffer access
  { OpCode::COPY, "COPY", "bb", nullptr, run_COPY },
  { OpCode::CLEAR, "CLEAR", "b", nullptr, run_CLEAR },
  { OpCode::MIX, "MIX", "bb", nullptr, run_MIX },
  { OpCode::MUL, "MUL", "bf", nullptr, run_MUL },
  { OpCode::SET_FLOAT, "SET_FLOAT", "bf", nullptr, run_SET_FLOAT },

  // I/O
  { OpCode::FETCH_CONTROL_VALUE, "FETCH_CONTROL_VALUE", "cb", nullptr, run_FETCH_CONTROL_VALUE },
  { OpCode::POST_RMS, "POST_RMS", "sib", nullptr, run_POST_RMS },

  // generators
  { OpCode::NOISE, "NOISE", "b", nullptr, run_NOISE },
  { OpCode::SINE, "SINE", "bf", nullptr, run_SINE },
  { OpCode::MIDI_MONKEY, "MIDI_MONKEY", "bf", nullptr, run_MIDI_MONKEY },

  // processors
  { OpCode::CONNECT_PORT, "CONNECT_PORT", "pib", init_CONNECT_PORT, nullptr },
  { OpCode::CALL, "CALL", "p", nullptr, run_CALL },

  // logging
  { OpCode::LOG_RMS, "LOG_RMS", "b", nullptr, run_LOG_RMS },
  { OpCode::LOG_ATOM, "LOG_ATOM", "b", nullptr, run_LOG_ATOM },
};

}  // namespace noisicaa
