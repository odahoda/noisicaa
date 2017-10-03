#include <iostream>
#include "capnp/serialize.h"
#include "noisicaa/core/perf_stats.h"
#include "noisicaa/audioproc/vm/backend_ipc.h"
#include "noisicaa/audioproc/vm/audio_stream.h"
#include "noisicaa/audioproc/vm/vm.h"

namespace noisicaa {

class IPCRequest {
public:
  IPCRequest(const string& request_bytes)
    : _request_bytes(request_bytes),
      _words(
	  (::capnp::word*)_request_bytes.c_str(),
	  _request_bytes.size() / sizeof(::capnp::word)),
      _reader(_words) {}

  capnp::BlockData::Reader reader() {
    return _reader.getRoot<capnp::BlockData>();
  }

private:
  string _request_bytes;
  kj::ArrayPtr<::capnp::word> _words;
  ::capnp::FlatArrayMessageReader _reader;
};

IPCBackend::IPCBackend(const BackendSettings& settings)
  : Backend("noisicaa.audioproc.vm.backend.ipc", settings),
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

  // The request bytes and capnp reader must stay alive until end_block, because
  // ctxt->buffers and ctxt->messages contain pointers into it.
  // Only way with capnp seems to be to create it on the heap...
  _request.reset(new IPCRequest(stor_request_bytes.result()));
  capnp::BlockData::Reader request = _request->reader();
  ctxt->perf->end_span();

  ctxt->buffers.clear();
  for (const auto& block : request.getBuffers()) {
    ::capnp::Data::Reader data = block.getData();
    ctxt->buffers.emplace(
        string(block.getId().cStr()),
	BlockContext::Buffer{data.size(), (const BufferPtr)data.begin()});
  }

  ctxt->in_messages.clear();
  for (const auto& msg : request.getMessages()) {
    ctxt->in_messages.emplace_back(string((const char*)msg.begin(), msg.size()));
  }

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
  _request.reset();

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
