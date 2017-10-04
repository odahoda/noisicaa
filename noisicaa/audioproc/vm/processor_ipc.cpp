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

#include <memory>
#include <string>
#include <assert.h>
#include <stdint.h>
#include "capnp/message.h"
#include "capnp/serialize.h"
#include "noisicaa/core/perf_stats.h"
#include "noisicaa/audioproc/vm/host_data.h"
#include "noisicaa/audioproc/vm/block_data.capnp.h"
#include "noisicaa/audioproc/vm/processor_ipc.h"

namespace noisicaa {

ProcessorIPC::ProcessorIPC(const string& node_id, HostData* host_data)
  : Processor(node_id, "noisicaa.audioproc.vm.processor.ipc", host_data) {}

ProcessorIPC::~ProcessorIPC() {}

Status ProcessorIPC::setup(const ProcessorSpec* spec) {
  Status status = Processor::setup(spec);
  RETURN_IF_ERROR(status);

  StatusOr<string> stor_or_address = get_string_parameter("ipc_address");
  RETURN_IF_ERROR(stor_or_address);
  string address = stor_or_address.result();

  _stream.reset(new AudioStreamClient(address));
  status = _stream->setup();
  RETURN_IF_ERROR(status);

  return Status::Ok();
}

void ProcessorIPC::cleanup() {
  if (_stream.get()) {
    _stream->cleanup();
    _stream.reset();
  }
  Processor::cleanup();
}

Status ProcessorIPC::connect_port(uint32_t port_idx, BufferPtr buf) {
  if (port_idx > 1) {
    return ERROR_STATUS("Invalid port index %d", port_idx);
  }
  _ports[port_idx] = buf;
  return Status::Ok();
}

Status ProcessorIPC::run(BlockContext* ctxt) {
  PerfTracker tracker(ctxt->perf.get(), "ipc");

  ::capnp::MallocMessageBuilder message_builder;
  capnp::BlockData::Builder request = message_builder.initRoot<capnp::BlockData>();
  request.setBlockSize(ctxt->block_size);
  request.setSamplePos(ctxt->sample_pos);

  {
    PerfTracker tracker(ctxt->perf.get(), "send_block");

    const auto& words = ::capnp::messageToFlatArray(message_builder);
    const auto& bytes = words.asChars();

    Status status = _stream->send_bytes(bytes.begin(), bytes.size());
    RETURN_IF_ERROR(status);
  }

  string bytes;
  {
    PerfTracker tracker(ctxt->perf.get(), "receive_block");
    StatusOr<string> stor_bytes = _stream->receive_bytes();
    RETURN_IF_ERROR(stor_bytes);
    bytes = stor_bytes.result();
  }
  assert(bytes.size() % sizeof(::capnp::word) == 0);
  kj::ArrayPtr<::capnp::word> words(
      (::capnp::word*)bytes.c_str(),
      bytes.size() / sizeof(::capnp::word));
  ::capnp::FlatArrayMessageReader message_reader(words);
  capnp::BlockData::Reader response = message_reader.getRoot<capnp::BlockData>();

  assert(response.getBlockSize() == ctxt->block_size);
  assert(response.getSamplePos() == ctxt->sample_pos);

  for (const auto& span : response.getPerfData().getSpans()) {
    ctxt->perf->append_span(
        PerfStats::Span{
          span.getId(),
          span.getName().cStr(),
          span.getParentId() != 0 ? span.getParentId() : ctxt->perf->current_span_id(),
          span.getStartTimeNSec(),
          span.getEndTimeNSec()});
  }

  bool ports_written[2] = { false, false };
  for (const auto& buffer : response.getBuffers()) {
    int p;
    if (buffer.getId() == "output:0") {
      p = 0;
    } else if (buffer.getId() == "output:1") {
      p = 1;
    } else {
      _logger->warning("Ignoring unexpected buffer %s", buffer.getId().cStr());
      continue;
    }

    assert(buffer.getData().size() == ctxt->block_size * sizeof(float));
    memmove(_ports[p], buffer.getData().begin(), ctxt->block_size * sizeof(float));
    ports_written[p] = true;
  }

  for (int p = 0 ; p < 2 ; ++p) {
    if (!ports_written[p]) {
      _logger->warning("Expected buffer output:%d not received", p);
      memset(_ports[p], 0, ctxt->block_size * sizeof(float));
    }
  }

  return Status::Ok();
}

}
