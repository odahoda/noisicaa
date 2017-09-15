#include <memory>
#include <string>
#include <assert.h>
#include <stdint.h>
#include "capnp/message.h"
#include "capnp/serialize.h"
#include "noisicore/host_data.h"
#include "noisicore/misc.h"
#include "noisicore/block_data.capnp.h"
#include "noisicore/processor_ipc.h"

namespace noisicaa {

ProcessorIPC::ProcessorIPC(HostData* host_data)
  : Processor(host_data) {}

ProcessorIPC::~ProcessorIPC() {}

Status ProcessorIPC::setup(const ProcessorSpec* spec) {
  Status status = Processor::setup(spec);
  if (status.is_error()) { return status; }

  StatusOr<string> stor_or_address = get_string_parameter("ipc_address");
  if (stor_or_address.is_error()) { return stor_or_address; }
  string address = stor_or_address.result();

  _stream.reset(new AudioStreamClient(address));
  status = _stream->setup();
  if (status.is_error()) { return status; }

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
    return Status::Error(sprintf("Invalid port index %d", port_idx));
  }
  _ports[port_idx] = buf;
  return Status::Ok();
}

Status ProcessorIPC::run(BlockContext* ctxt) {
  // with ctxt.perf.track('ipc'):

  capnp::BlockData::Builder request = _stream->block_data_builder();
  request.setBlockSize(ctxt->block_size);
  request.setSamplePos(ctxt->sample_pos);
  //     with ctxt.perf.track('ipc.send_block'):
  Status status = _stream->send_block(request);
  if (status.is_error()) { return status; }

  //     with ctxt.perf.track('ipc.receive_block'):
  StatusOr<string> stor_bytes = _stream->receive_bytes();
  if (stor_bytes.is_error()) { return stor_bytes; }
  string bytes = stor_bytes.result();
  assert(bytes.size() % sizeof(::capnp::word) == 0);
  kj::ArrayPtr<::capnp::word> words(
      (::capnp::word*)bytes.c_str(),
      bytes.size() / sizeof(::capnp::word));
  ::capnp::FlatArrayMessageReader message_reader(words);
  capnp::BlockData::Reader response = message_reader.getRoot<capnp::BlockData>();

  assert(response.getBlockSize() == ctxt->block_size);
  assert(response.getSamplePos() == ctxt->sample_pos);

  //     ctxt.perf.add_spans(response.perfData)

  bool ports_written[2] = { false, false };
  for (const auto& buffer : response.getBuffers()) {
    int p;
    if (buffer.getId() == "output:0") {
      p = 0;
    } else if (buffer.getId() == "output:1") {
      p = 1;
    } else {
      log(LogLevel::WARNING, "Ignoring unexpected buffer %s", buffer.getId().cStr());
      continue;
    }

    assert(buffer.getData().size() == ctxt->block_size * sizeof(float));
    memmove(_ports[p], buffer.getData().begin(), ctxt->block_size * sizeof(float));
    ports_written[p] = true;
  }

  for (int p = 0 ; p < 2 ; ++p) {
    if (!ports_written[p]) {
      log(LogLevel::WARNING, "Expected buffer output:%d not received", p);
      memset(_ports[p], 0, ctxt->block_size * sizeof(float));
    }
  }

  return Status::Ok();
}

}
