#include "misc.h"

#include <memory>
#include <stdio.h>
#include <stdarg.h>

using std::string;
using std::unique_ptr;

namespace noisicaa {

string sprintf(const string &fmt, ...) {
  va_list args;
  va_start(args, fmt);

  int size = std::vsnprintf(nullptr, 0, fmt.c_str(), args) + 1;
  unique_ptr<char> buf(new char[size]);
  std::vsnprintf(buf.get(), size, fmt.c_str(), args);
  return string(buf.get());
}

}
