#ifndef _NOISICORE_MISC_H
#define _NOISICORE_MISC_H

#include <string>

namespace noisicaa {

std::string sprintf(const std::string& fmt, ...);

enum LogLevel {
  INFO, WARNING, ERROR
};

void log(LogLevel log_level, const char* fmt, ...);

}  // namespace noisicaa

#endif
