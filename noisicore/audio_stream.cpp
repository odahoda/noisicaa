#include <string>
#include <poll.h>
#include <unistd.h>
#include <fcntl.h>
#include <stdlib.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <sys/types.h>

#include "audio_stream.h"
#include "misc.h"

namespace {

using namespace noisicaa;

Status set_blocking(int fd, int blocking) {
  int arg = !blocking;
  int rc = ioctl(fd, FIONBIO, &arg);
  if (rc < 0) {
    return Status::Error(sprintf("Failed ioctl on FD %d: %d", fd, rc));
  }
  return Status::Ok();
}

}  // anonymous namespace

namespace noisicaa {

AudioStreamBase::AudioStreamBase(const string& address)
  : _address(address) {}

AudioStreamBase::~AudioStreamBase() {
  cleanup();
}

Status AudioStreamBase::setup() {
  return Status::Ok();
}

void AudioStreamBase::cleanup() {
  _buffer.erase();
}

void AudioStreamBase::close() {
  _closed = true;
}

Status AudioStreamBase::fill_buffer() {
  while (true) {
    struct pollfd fds = {_pipe_in, POLLIN, 0};
    int rc = poll(&fds, 1, 500);
    if (rc < 0) {
      return Status::Error(sprintf("Failed to poll in pipe: %d", rc));
    }

    if (fds.revents & POLLIN) {
      char buf[1024];
      ssize_t num_bytes = read(_pipe_in, buf, sizeof(buf));
      _buffer.append(buf, num_bytes);
      return Status::Ok();
    } else if (fds.revents & POLLHUP) {
      log(LogLevel::WARNING, "Pipe disconnected");
      return Status::Error("Stream closed");
    }

    if (_closed) {
      return Status::Error("Stream closed");
    }
  }
}

StatusOr<string> AudioStreamBase::get_line() {
  while (true) {
    size_t eol = _buffer.find('\n');
    if (eol != string::npos) {
      string line = _buffer.substr(0, eol);
      _buffer.erase(0, eol + 1);
      return line;
    }

    Status status = fill_buffer();
    if (status.is_error()) { return status; }
  }
}

StatusOr<string> AudioStreamBase::get_bytes(size_t num_bytes) {
  while (_buffer.size() < num_bytes) {
    Status status = fill_buffer();
    if (status.is_error()) { return status; }
  }

  string data = _buffer.substr(0, num_bytes);
  _buffer.erase(0, num_bytes);
  return data;
}

StatusOr<string> AudioStreamBase::receive_frame_bytes() {
  StatusOr<string> line_or_status = get_line();
  if (line_or_status.is_error()) { return line_or_status; }
  string line = line_or_status.result();

  if (line == "#CLOSE") {
    return Status::Error("Stream closed");
  }

  assert(line.substr(0, 5) == "#LEN=");
  int len = atoi(line.substr(5).c_str());

  StatusOr<string> payload_or_status = get_bytes(len);
  if (payload_or_status.is_error()) { return payload_or_status; }
  string payload = payload_or_status.result();

  line_or_status = get_line();
  if (line_or_status.is_error()) { return line_or_status; }
  line = line_or_status.result();
  assert(line == "#END");

  return payload;
}

StatusOr<string> AudioStreamBase::receive_frame() {
  // TODO: deserialize frame
  return receive_frame_bytes();
}

Status AudioStreamBase::send_frame_bytes(const string& frame_bytes) {
  string request;
  request += sprintf("#LEN=%d\n", frame_bytes.size());
  request += frame_bytes;
  request += "#END\n";

  while (request.size() > 0) {
    ssize_t bytes_written = write(_pipe_out, request.c_str(), request.size());
    if (bytes_written < 0) {
      return Status::Error("Failed to write to pipe.");
    }
    request.erase(0, bytes_written);
  }

  return Status::Ok();
}

Status AudioStreamBase::send_frame(const string& frame) {
  // TODO: serialize frame
  return send_frame_bytes(frame);
}

AudioStreamServer::AudioStreamServer(const string& address)
  : AudioStreamBase(address) {}

Status AudioStreamServer::setup() {
//         logger.info("Serving from %s", self._address)

  int rc;
  Status status;

  string address_in = _address + ".send";
  string address_out = _address + ".recv";

  rc = mkfifo(address_in.c_str(), 0600);
  if (rc != 0) {
    return Status::Error(sprintf("Failed to create %s: %d", address_in.c_str(), rc));
  }

  _pipe_in = open(address_in.c_str(), O_RDONLY | O_NONBLOCK);
  if (_pipe_in < 0) {
    return Status::Error(sprintf("Failed to open %s: %d", address_in.c_str(), _pipe_in));
  }
  status = set_blocking(_pipe_in, true);
  if (status.is_error()) { return status; }

  rc = mkfifo(address_out.c_str(), 0600);
  if (rc != 0) {
    return Status::Error(sprintf("Failed to create %s: %d", address_out.c_str(), rc));
  }

  _pipe_out = open(address_out.c_str(), O_RDWR | O_NONBLOCK);
  if (_pipe_out < 0) {
    return Status::Error(sprintf("Failed to open %s: %d", address_out.c_str(), _pipe_out));
  }
  status = set_blocking(_pipe_out, true);
  if (status.is_error()) { return status; }

  return AudioStreamBase::setup();

  //         logger.info("Server ready.")
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
  : AudioStreamBase(address) {}

Status AudioStreamClient::setup() {
//         logger.info("Connecting to %s...", self._address)
  Status status;

  string address_in = _address + ".recv";
  string address_out = _address + ".send";

  _pipe_in = open(address_in.c_str(), O_RDONLY | O_NONBLOCK);
  if (_pipe_in < 0) {
    return Status::Error(sprintf("Failed to open %s: %d", address_in.c_str(), _pipe_in));
  }
  status = set_blocking(_pipe_in, true);
  if (status.is_error()) { return status; }

  _pipe_out = open(address_out.c_str(), O_RDWR | O_NONBLOCK);
  if (_pipe_out < 0) {
    return Status::Error(sprintf("Failed to open %s: %d", address_out.c_str(), _pipe_out));
  }
  status = set_blocking(_pipe_out, true);
  if (status.is_error()) { return status; }

  return AudioStreamBase::setup();
}

void AudioStreamClient::cleanup() {
  AudioStreamBase::cleanup();

  if (_pipe_out >= 0) {
    string request = "#CLOSE\n";
    while (request.size() > 0) {
      ssize_t bytes_written = write(_pipe_out, request.c_str(), request.size());
      if (bytes_written < 0) {
	log(LogLevel::ERROR, "Failed to write to pipe.");
	break;
      }
      request.erase(0, bytes_written);
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
