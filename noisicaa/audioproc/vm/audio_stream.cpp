#include <iostream>
#include <string>
#include <poll.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdlib.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <sys/types.h>
#include "noisicaa/audioproc/vm/audio_stream.h"
#include "noisicaa/audioproc/vm/misc.h"

namespace {

using namespace noisicaa;

Status set_blocking(int fd, int blocking) {
  int arg = !blocking;
  int rc = ioctl(fd, FIONBIO, &arg);
  if (rc < 0) {
    // TODO: Status::ErrorFromErrno
    return Status::Error("Failed ioctl on FD %d: %d", fd, rc);
  }
  return Status::Ok();
}

}  // anonymous namespace

namespace noisicaa {

AudioStreamBase::AudioStreamBase(const char* logger_name, const string& address)
  : _logger(LoggerRegistry::get_logger(logger_name)),
    _address(address) {}

AudioStreamBase::~AudioStreamBase() {
  cleanup();
}

Status AudioStreamBase::setup() {
  return Status::Ok();
}

void AudioStreamBase::cleanup() {
}

void AudioStreamBase::close() {
  _closed = true;
}

Status AudioStreamBase::pipe_read(char* data, size_t size) {
  if (_closed) {
    return Status::ConnectionClosed();
  }

  while (size > 0) {
    struct pollfd fds = {_pipe_in, POLLIN, 0};
    int rc = poll(&fds, 1, 500);
    if (rc < 0) {
      // TODO: Status::ErrorFromErrno
      return Status::Error("Failed to poll in pipe: %d", rc);
    }

    if (_closed) {
      return Status::ConnectionClosed();
    }

    if (fds.revents & POLLIN) {
      ssize_t bytes_read = read(_pipe_in, data, size);
      if (bytes_read < 0) {
	// TODO: Status::ErrorFromErrno
	return Status::Error("Failed to read from pipe.");
      }
      data += bytes_read;
      size -= bytes_read;
    } else if (fds.revents & POLLHUP) {
      return Status::ConnectionClosed();
    }
  }

  return Status::Ok();
}

Status AudioStreamBase::pipe_write(const char* data, size_t size) {
  if (_closed) {
    return Status::ConnectionClosed();
  }

  while (size > 0) {
    struct pollfd fds = {_pipe_out, POLLOUT, 0};
    int rc = poll(&fds, 1, 500);
    if (rc < 0) {
      // TODO: Status::ErrorFromErrno
      return Status::Error("Failed to poll out pipe: %d", rc);
    }

    if (_closed) {
      return Status::ConnectionClosed();
    }

    if (fds.revents & POLLOUT) {
      ssize_t bytes_written = write(_pipe_out, data, size);
      if (bytes_written < 0) {
	// TODO: Status::ErrorFromErrno
	return Status::Error("Failed to write to pipe.");
      }
      data += bytes_written;
      size -= bytes_written;
    } else if (fds.revents & POLLHUP) {
      return Status::ConnectionClosed();
    }
  }

  return Status::Ok();
}

StatusOr<string> AudioStreamBase::receive_bytes() {
  Status status;

  uint32_t magic;
  status = pipe_read((char*)&magic, sizeof(magic));
  if (status.is_error()) { return status; }

  if (magic == CLOSE) {
    return Status::ConnectionClosed();
  } else if (magic == BLOCK_START) {
    uint32_t num_bytes;
    status = pipe_read((char*)&num_bytes, sizeof(num_bytes));
    if (status.is_error()) { return status; }

    string payload;
    payload.resize(num_bytes);
    status = pipe_read((char*)payload.data(), num_bytes);
    if (status.is_error()) { return status; }

    return payload;
  } else {
    return Status::Error("Unexpected magic token %08x", magic);
  }
}

Status AudioStreamBase::send_bytes(const char* data, size_t size) {
  Status status;

  if (size > 1 << 30) {
    return Status::Error("Block too large (%d bytes)", size);
  }

  uint32_t header[2] = { BLOCK_START, (uint32_t)size };
  status = pipe_write((const char*)header, sizeof(header));
  if (status.is_error()) { return status; }

  status = pipe_write(data, size);
  if (status.is_error()) { return status; }

  return Status::Ok();
}

AudioStreamServer::AudioStreamServer(const string& address)
  : AudioStreamBase("noisicaa.audioproc.vm.audio_stream.server", address) {}

Status AudioStreamServer::setup() {
  _logger->info("Serving from %s", _address.c_str());

  int rc;
  Status status;

  string address_in = _address + ".send";
  string address_out = _address + ".recv";

  rc = mkfifo(address_in.c_str(), 0600);
  if (rc != 0) {
    return Status::Error("Failed to create %s: %d", address_in.c_str(), rc);
  }

  _pipe_in = open(address_in.c_str(), O_RDONLY | O_NONBLOCK);
  if (_pipe_in < 0) {
    return Status::Error("Failed to open %s: %d", address_in.c_str(), _pipe_in);
  }
  status = set_blocking(_pipe_in, true);
  if (status.is_error()) { return status; }

  rc = mkfifo(address_out.c_str(), 0600);
  if (rc != 0) {
    return Status::Error("Failed to create %s: %d", address_out.c_str(), rc);
  }

  _pipe_out = open(address_out.c_str(), O_RDWR | O_NONBLOCK);
  if (_pipe_out < 0) {
    return Status::Error("Failed to open %s: %d", address_out.c_str(), _pipe_out);
  }
  status = set_blocking(_pipe_out, true);
  if (status.is_error()) { return status; }

  _logger->info("Server ready.");

  return AudioStreamBase::setup();
}

void AudioStreamServer::cleanup() {
  AudioStreamBase::cleanup();

  if (_pipe_in >= 0) {
    ::close(_pipe_in);
    _pipe_in = -1;
  }

  if (_pipe_out >= 0) {
    ::close(_pipe_out);
    _pipe_out = -1;
  }

//         if os.path.exists(self._address + '.send'):
//             os.unlink(self._address + '.send')

//         if os.path.exists(self._address + '.recv'):
//             os.unlink(self._address + '.recv')
}

AudioStreamClient::AudioStreamClient(const string& address)
  : AudioStreamBase("noisicaa.audioproc.vm.audio_stream.client", address) {}

Status AudioStreamClient::setup() {
  _logger->info("Connecting to %s...", _address.c_str());

  Status status;

  string address_in = _address + ".recv";
  string address_out = _address + ".send";

  _pipe_in = open(address_in.c_str(), O_RDONLY | O_NONBLOCK);
  if (_pipe_in < 0) {
    return Status::Error("Failed to open %s: %d", address_in.c_str(), _pipe_in);
  }
  status = set_blocking(_pipe_in, true);
  if (status.is_error()) { return status; }

  _pipe_out = open(address_out.c_str(), O_RDWR | O_NONBLOCK);
  if (_pipe_out < 0) {
    return Status::Error("Failed to open %s: %d", address_out.c_str(), _pipe_out);
  }
  status = set_blocking(_pipe_out, true);
  if (status.is_error()) { return status; }

  return AudioStreamBase::setup();
}

void AudioStreamClient::cleanup() {
  AudioStreamBase::cleanup();

  if (_pipe_out >= 0) {
    uint32_t header[1] = { CLOSE };
    Status status = pipe_write((const char*)header, sizeof(header));
    if (status.is_error()) {
      _logger->error("Failed to write close message to pipe: %s", status.message());
    }

    ::close(_pipe_out);
    _pipe_out = -1;
  }

  if (_pipe_in) {
    ::close(_pipe_in);
    _pipe_in = -1;
  }
}

}  // namespace noisicaa
