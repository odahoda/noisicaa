#include <memory>
#include <string>
#include <assert.h>
#include <stdint.h>
#include "noisicaa/core/perf_stats.h"
#include "noisicaa/audioproc/vm/host_data.h"
#include "noisicaa/audioproc/vm/processor_lv2.h"

namespace noisicaa {

ProcessorLV2::ProcessorLV2(HostData* host_data)
  : Processor("noisicaa.audioproc.vm.processor.lv2", host_data) {}

ProcessorLV2::~ProcessorLV2() {}

Status ProcessorLV2::setup(const ProcessorSpec* spec) {
  Status status = Processor::setup(spec);
  if (status.is_error()) { return status; }

  StatusOr<string> stor_uri = get_string_parameter("lv2_uri");
  if (stor_uri.is_error()) { return stor_uri; }
  string uri = stor_uri.result();

  LilvWorld *world = _host_data->lv2->lilv_world;
  assert(world != nullptr);

  const LilvPlugins* all_plugins = lilv_world_get_all_plugins(world);

  LilvNode* uri_node = lilv_new_uri(world, uri.c_str());
  _plugin = lilv_plugins_get_by_uri(all_plugins, uri_node);
  lilv_free(uri_node);
  if (_plugin == nullptr) {
    return Status::Error("Plugin '%s' not found.", uri.c_str());
  }

  // TODO: use features from host data.
  _instance = lilv_plugin_instantiate(_plugin, 44100.0, nullptr);
  if (_instance == nullptr) {
    return Status::Error("Failed to instantiate '%s'.", uri.c_str());
  }

  lilv_instance_activate(_instance);

  return Status::Ok();
}

void ProcessorLV2::cleanup() {
  if (_instance != nullptr) {
    lilv_instance_deactivate(_instance);
    lilv_instance_free(_instance);
    _instance = nullptr;
  }

  if (_plugin != nullptr) {
    _plugin = nullptr;
  }
  Processor::cleanup();
}

Status ProcessorLV2::connect_port(uint32_t port_idx, BufferPtr buf) {
  lilv_instance_connect_port(_instance, port_idx, buf);
  return Status::Ok();
}

Status ProcessorLV2::run(BlockContext* ctxt) {
  PerfTracker tracker(ctxt->perf.get(), "lv2");
  lilv_instance_run(_instance, ctxt->block_size);
  return Status::Ok();
}

}
