#include <iostream>
#include "capnp/serialize.h"
#include "noisicaa/core/perf_stats.h"
#include "noisicore/backend_ipc.h"
#include "noisicore/audio_stream.h"
#include "noisicore/vm.h"

namespace noisicaa {

IPCBackend::IPCBackend(const BackendSettings& settings)
  : Backend("noisicore.backend.ipc", settings),
    _block_size(settings.block_size) {}

IPCBackend::~IPCBackend() {}

Status IPCBackend::setup(VM* vm) {
  Status status = Backend::setup(vm);
  if (status.is_error()) { return status; }

  if (_block_size == 0) {
   return Status::Error("Invalid block_size %d", _block_size);
  }

  if (_settings.ipc_address.size() == 0) {
    return Status::Error("ipc_address not set.");
  }

  _stream.reset(new AudioStreamServer(_settings.ipc_address));
  status = _stream->setup();
  if (status.is_error()) { return status; }

  for (int c = 0 ; c < 2 ; ++c) {
    _samples[c].reset(new BufferData[_block_size * sizeof(float)]);
  }

  vm->set_block_size(_block_size);

  return Status::Ok();
}

void IPCBackend::cleanup() {
  if (_stream.get() != nullptr) {
    _stream->cleanup();
    _stream.reset();
  }

  Backend::cleanup();
}

Status IPCBackend::begin_block(BlockContext* ctxt) {
  StatusOr<string> stor_request_bytes = _stream->receive_bytes();

  assert(ctxt->perf->current_span_id() == 0);
  ctxt->perf->start_span("frame");

  if (stor_request_bytes.is_connection_closed()) {
    _logger->warning("Stopping IPC backend...");
    stop();
    return Status::Ok();
  }
  if (stor_request_bytes.is_error()) { return stor_request_bytes; }

  ctxt->perf->start_span("parse_request");
  string request_bytes = stor_request_bytes.result();
  kj::ArrayPtr<::capnp::word> words(
      (::capnp::word*)request_bytes.c_str(),
      request_bytes.size() / sizeof(::capnp::word));
  ::capnp::FlatArrayMessageReader message_reader(words);
  capnp::BlockData::Reader request(message_reader.getRoot<capnp::BlockData>());
  ctxt->perf->end_span();

  ctxt->buffers.clear();
  for (const auto& block : request.getBuffers()) {
    ::capnp::Data::Reader data = block.getData();
    ctxt->buffers.emplace(string(block.getId().cStr()), BlockContext::Buffer{data.size(), (const BufferPtr)data.begin()});
  }

  //     ctxt.messages = in_frame.messages

  // TODO: Is there a way to reuse and reset an existing message builder, without
  // memory bloat?
  _message_builder.reset(new ::capnp::MallocMessageBuilder());
  _out_block = _message_builder->initRoot<capnp::BlockData>();
  _out_block.setBlockSize(request.getBlockSize());
  _out_block.setSamplePos(request.getSamplePos());

  if (_block_size != request.getBlockSize()) {
    PerfTracker tracker(ctxt->perf.get(), "resize_buffers");

    _logger->info("Block size changed %d -> %d", _block_size, request.getBlockSize());
    _block_size = request.getBlockSize();
    for (int c = 0 ; c < 2 ; ++c) {
      _samples[c].reset(new BufferData[_block_size * sizeof(float)]);
    }
    Status status = _vm->set_block_size(_block_size);
    if (status.is_error()) { return status; }
  }

  for (int c = 0 ; c < 2 ; ++c) {
    _channel_written[c] = false;
  }

  return Status::Ok();
}

Status IPCBackend::end_block(BlockContext* ctxt) {
  int num_buffers = 0;
  for (int c = 0 ; c < 2 ; ++c) {
    if (_channel_written[c]) {
      ++num_buffers;
    }
  }

  auto buffers = _out_block.initBuffers(num_buffers);
  int b = 0;
  for (int c = 0 ; c < 2 ; ++c) {
    if (_channel_written[c]) {
      auto buffer = buffers[b];

      char id[64];
      snprintf(id, sizeof(id), "output:%d", b);
      buffer.setId(id);

      auto data = buffer.initData(_block_size * sizeof(float));
      memmove(data.begin(), _samples[c].get(), _block_size * sizeof(float));

      ++b;
    }
  }

  ctxt->perf->end_span();

  assert(ctxt->perf->current_span_id() == 0);
  auto spans = _out_block.getPerfData().initSpans(ctxt->perf->num_spans());
  for (int i = 0 ; i < ctxt->perf->num_spans() ; ++i) {
    const auto& ispan = ctxt->perf->span(i);
    auto ospan = spans[i];
    ospan.setId(ispan.id);
    ospan.setName(ispan.name);
    ospan.setParentId(ispan.parent_id);
    ospan.setStartTimeNSec(ispan.start_time_nsec);
    ospan.setEndTimeNSec(ispan.end_time_nsec);
  }

  if (!stopped()) {
    const auto& words = ::capnp::messageToFlatArray(*_message_builder.get());
    const auto& bytes = words.asChars();

    Status status = _stream->send_bytes(bytes.begin(), bytes.size());
    if (status.is_error()) { return status; }
  }

  return Status::Ok();
}

Status IPCBackend::output(BlockContext* ctxt, const string& channel, BufferPtr samples) {
  int c;
  if (channel == "left") {
    c = 0;
  } else if (channel == "right") {
    c = 1;
  } else {
    return Status::Error("Invalid channel %s", channel.c_str());
  }

  if (_channel_written[c]) {
    return Status::Error("Channel %s written multiple times.", channel.c_str());
  }
  _channel_written[c] = true;
  memmove(_samples[c].get(), samples, _block_size * sizeof(float));

  return Status::Ok();
}

}  // namespace noisicaa
