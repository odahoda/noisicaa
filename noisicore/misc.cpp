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

  va_start(args, fmt);
  std::vsnprintf(buf.get(), size, fmt.c_str(), args);
  return string(buf.get());
}

void log(LogLevel log_level, const char* fmt, ...) {
  switch (log_level) {
  case LogLevel::INFO:    printf("INFO: ");    break;
  case LogLevel::WARNING: printf("WARNING: "); break;
  case LogLevel::ERROR:   printf("ERROR: ");   break;
  }

  va_list args;
  va_start(args, fmt);
  std::vprintf(fmt, args);
  std::printf("\n");
}

}
