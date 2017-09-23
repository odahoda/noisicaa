#include <stdarg.h>
#include "noisicaa/core/status.h"

namespace noisicaa {

Status Status::Error(const char* fmt, ...) {
  va_list args;
  va_start(args, fmt);

  char msg[10240];
  vsnprintf(msg, sizeof(msg), fmt, args);

  return Error(string(msg));
}

}  // namespace noisicaa

