#include <memory>
#include <stdio.h>
#include <stdarg.h>
#include "noisicaa/audioproc/vm/misc.h"

namespace noisicaa {

string sprintf(const string &fmt, ...) {
  va_list args;
  va_start(args, fmt);

  int size = std::vsnprintf(nullptr, 0, fmt.c_str(), args) + 1;
  unique_ptr<char> buf(new char[size]);

  va_start(args, fmt);
  std::vsnprintf(buf.get(), size, fmt.c_str(), args);
  return string(buf.get());
}

}
