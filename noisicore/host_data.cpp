#include <assert.h>
#include "noisicore/host_data.h"

namespace noisicaa {

HostData::HostData()
  : lv2(new LV2SubSystem()) {}

HostData::~HostData() {
  cleanup();
}

Status HostData::setup() {
  Status status;

  status = lv2->setup();
  if (status.is_error()) { return status; }

  return Status::Ok();
}

void HostData::cleanup() {
  lv2->cleanup();
}

}  // namespace noisicaa
