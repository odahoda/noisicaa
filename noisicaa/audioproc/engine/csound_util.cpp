/*
 * @begin:license
 *
 * Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License along
 * with this program; if not, write to the Free Software Foundation, Inc.,
 * 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
 *
 * @end:license
 */

#include <assert.h>
#include <stdint.h>
#include <string.h>
#include "noisicaa/core/logging.h"
#include "noisicaa/core/perf_stats.h"
#include "noisicaa/host_system/host_system.h"
#include "noisicaa/audioproc/engine/csound_util.h"
#include "noisicaa/audioproc/engine/rtcheck.h"

namespace noisicaa {

CSoundUtil::CSoundUtil(HostSystem* host_system)
  : _logger(LoggerRegistry::get_logger("noisicaa.audioproc.engine.csound_util")),
    _host_system(host_system) {}

CSoundUtil::~CSoundUtil() {
  if (_csnd != nullptr) {
    _logger->info("Destroying csound instance %p", _csnd);
    csoundDestroy(_csnd);
  }
  _event_input_ports.clear();
}

void CSoundUtil::_log_cb(CSOUND* csnd, int attr, const char* fmt, va_list args) {
  CSoundUtil* proc = (CSoundUtil*)csoundGetHostData(csnd);
  assert(proc != nullptr);
  proc->_log_cb(attr, fmt, args);
}

void CSoundUtil::_log_cb(int attr, const char* fmt, va_list args) {
  LogLevel level = LogLevel::INFO;
  switch (attr & CSOUNDMSG_TYPE_MASK) {
  case CSOUNDMSG_ORCH:
  case CSOUNDMSG_REALTIME:
  case CSOUNDMSG_DEFAULT:
    level = LogLevel::INFO;
    break;
  case CSOUNDMSG_WARNING:
    level = LogLevel::WARNING;
    break;
  case CSOUNDMSG_ERROR:
    level = LogLevel::ERROR;
    break;
  }

  size_t bytes_used = strlen(_log_buf);
  vsnprintf(_log_buf + bytes_used, sizeof(_log_buf) - bytes_used, fmt, args);

  while (_log_buf[0]) {
    char *eol = strchr(_log_buf, '\n');
    if (eol == nullptr) {
      break;
    }

    *eol = 0;
    _logger->log(level, "%s", _log_buf);

    memmove(_log_buf, eol + 1, strlen(eol + 1) + 1);
  }
}

Status CSoundUtil::setup(
    const string& orchestra, const string& score, const vector<PortSpec>& ports) {
  _ports = ports;

  memset(_log_buf, 0, sizeof(_log_buf));
  _event_input_ports.resize(_ports.size());

  _csnd = csoundCreate(this);
  if (_csnd == nullptr) {
    return ERROR_STATUS("Failed to create Csound instance.");
  }
  _logger->info("Created csound instance %p", _csnd);

  csoundSetMessageCallback(_csnd, CSoundUtil::_log_cb);

  int rc = csoundSetOption(_csnd, "-n");
  if (rc < 0) {
    return ERROR_STATUS("Failed to set Csound options (code %d)", rc);
  }

  _logger->info("csound orchestra:\n%s", orchestra.c_str());
  rc = csoundCompileOrc(_csnd, orchestra.c_str());
  if (rc < 0) {
    return ERROR_STATUS("Failed to compile Csound orchestra (code %d)", rc);
  }

  double zerodbfs = csoundGet0dBFS(_csnd);
  if (zerodbfs != 1.0) {
    return ERROR_STATUS("Csound orchestra must set 0dbfs=1.0 (found %f)", zerodbfs);
  }

  rc = csoundStart(_csnd);
  if (rc < 0) {
    return ERROR_STATUS("Failed to start Csound (code %d)", rc);
  }

  _logger->info("csound score:\n%s", score.c_str());
  rc = csoundReadScore(_csnd, score.c_str());
  if (rc < 0) {
    return ERROR_STATUS("Failed to read Csound score (code %d)", rc);
  }

  _channel_ptr.resize(_ports.size());
  _channel_lock.resize(_ports.size());
  for (size_t port_idx = 0 ; port_idx < _ports.size() ; ++port_idx) {
    const auto& port = _ports[port_idx];

    if (port.type == pb::PortDescription::EVENTS) {
      continue;
    }

    MYFLT* channel_ptr;
    int type = csoundGetChannelPtr(_csnd, &channel_ptr, port.name.c_str(), 0);
    if (type < 0) {
      return ERROR_STATUS("Orchestra does not define the channel '%s'", port.name.c_str());
    }

    if (port.direction == pb::PortDescription::OUTPUT
        && !(type & CSOUND_OUTPUT_CHANNEL)) {
      return ERROR_STATUS("Channel '%s' is not an output channel", port.name.c_str());
    }

    if (port.direction == pb::PortDescription::INPUT
        && !(type & CSOUND_INPUT_CHANNEL)) {
      return ERROR_STATUS("Channel '%s' is not an input channel", port.name.c_str());
    }

    if (port.type == pb::PortDescription::AUDIO
        || port.type == pb::PortDescription::ARATE_CONTROL) {
      if ((type & CSOUND_CHANNEL_TYPE_MASK) != CSOUND_AUDIO_CHANNEL) {
        return ERROR_STATUS("Channel '%s' is not an audio channel", port.name.c_str());
      }
    } else if (port.type == pb::PortDescription::KRATE_CONTROL) {
      if ((type & CSOUND_CHANNEL_TYPE_MASK) != CSOUND_CONTROL_CHANNEL) {
        return ERROR_STATUS("Channel '%s' is not an control channel", port.name.c_str());
      }
    } else {
      return ERROR_STATUS("Internal error, channel '%s' type %d", port.name.c_str(), port.type);
    }

    int rc = csoundGetChannelPtr(_csnd, &channel_ptr, port.name.c_str(), type);
    if (rc < 0) {
      return ERROR_STATUS("Failed to get channel pointer for port '%s'", port.name.c_str());
    }
    assert(channel_ptr != nullptr);

    _channel_ptr[port_idx] = channel_ptr;
    _channel_lock[port_idx] = csoundGetChannelLock(_csnd, port.name.c_str());
  }

  return Status::Ok();
}

Status CSoundUtil::process_block(
    BlockContext* ctxt, TimeMapper* time_mapper, vector<BufferPtr>& buffers) {
  assert(buffers.size() == (size_t)_ports.size());

  for (size_t port_idx = 0 ; port_idx < _ports.size() ; ++port_idx) {
    const auto& port = _ports[port_idx];
    if (port.direction == pb::PortDescription::INPUT
        && port.type == pb::PortDescription::EVENTS) {
      LV2_Atom_Sequence* seq = (LV2_Atom_Sequence*)buffers[port_idx];
      if (seq->atom.type != _host_system->lv2->urid.atom_sequence) {
        return ERROR_STATUS(
            "Excepted sequence in port '%s', got %d.", port.name.c_str(), seq->atom.type);
      }
      LV2_Atom_Event* event = lv2_atom_sequence_begin(&seq->body);
      int instr = 1; // TODO: use port.csound_instr
      _event_input_ports[port_idx] = {seq, event, instr};
    }
  }

  uint32_t pos = 0;
  uint32_t ksmps = csoundGetKsmps(_csnd);
  while (pos < _host_system->block_size()) {
    // Copy input ports into Csound channels.
    for (size_t port_idx = 0 ; port_idx < _ports.size() ; ++port_idx) {
      const auto& port = _ports[port_idx];
      if (port.direction == pb::PortDescription::INPUT) {
        switch (port.type) {
        case pb::PortDescription::AUDIO:
        case pb::PortDescription::ARATE_CONTROL: {
          float* buf = (float*)buffers[port_idx];
          buf += pos;

          MYFLT* channel_ptr = _channel_ptr[port_idx];
          int *lock = _channel_lock[port_idx];
          csoundSpinLock(lock);
          for (uint32_t i = 0 ; i < ksmps ; ++i) {
            *channel_ptr++ = *buf++;
          }
          csoundSpinUnLock(lock);
          break;
        }

        case pb::PortDescription::KRATE_CONTROL: {
          float* buf = (float*)buffers[port_idx];

          MYFLT* channel_ptr = _channel_ptr[port_idx];
          int *lock = _channel_lock[port_idx];
          csoundSpinLock(lock);
          *channel_ptr = *buf;
          csoundSpinUnLock(lock);
          break;
        }

        case pb::PortDescription::EVENTS: {
          EventInputPort &ep = _event_input_ports[port_idx];

          // TODO: is instrument started with one ksmps delay? needs further testing.
          while (!lv2_atom_sequence_is_end(
                     &ep.seq->body, ep.seq->atom.size, ep.event)
                 && ep.event->time.frames < pos + ksmps) {
            LV2_Atom& atom = ep.event->body;
            if (atom.type == _host_system->lv2->urid.midi_event) {
              uint8_t* midi = (uint8_t*)LV2_ATOM_CONTENTS(LV2_Atom, &atom);
              if ((midi[0] & 0xf0) == 0x90) {
                MYFLT p[5] = {
                  /* p1: instr    */ (MYFLT)ep.instr + (MYFLT)midi[1] / 1000.0,
                  /* p2: time     */ 0.0,
                  /* p3: duration */ -1.0,
                  /* p4: pitch    */ (MYFLT)midi[1],
                  /* p5: velocity */ (MYFLT)midi[2],
                };
                //_logger->info("i %f %f %f %f %f", p[0], p[1], p[2], p[3], p[4]);
                int rc = csoundScoreEvent(_csnd, 'i', p, 5);
                if (rc < 0) {
                  return ERROR_STATUS("csoundScoreEvent failed (code %d).", rc);
                }
              } else if ((midi[0] & 0xf0) == 0x80) {
                MYFLT p[3] = {
                  /* p1: instr    */ -((MYFLT)ep.instr + (MYFLT)midi[1] / 1000.0),
                  /* p2: time     */ 0.0,
                  /* p3: duration */ 0.0,
                };
                //_logger->info("i %f %f %f", p[0], p[1], p[2]);
                int rc = csoundScoreEvent(_csnd, 'i', p, 3);
                if (rc < 0) {
                  return ERROR_STATUS("csoundScoreEvent failed (code %d).", rc);
                }
              } else {
                _logger->warning("Ignoring unsupported midi event %d.", midi[0] & 0xf0);
              }
            } else {
              _logger->warning("Ignoring event %d in sequence.", atom.type);
            }
            ep.event = lv2_atom_sequence_next(ep.event);
          }
          break;
        }

        default:
          return ERROR_STATUS("Port %s has unsupported type %d", port.name.c_str(), port.type);
        }
      } else {
        assert(port.direction == pb::PortDescription::OUTPUT);

        switch (port.type) {
        case pb::PortDescription::AUDIO:
        case pb::PortDescription::ARATE_CONTROL: {
          MYFLT* channel_ptr = _channel_ptr[port_idx];
          int *lock = _channel_lock[port_idx];
          csoundSpinLock(lock);
          for (uint32_t i = 0 ; i < ksmps ; ++i) {
            *channel_ptr++ = 0.0;
          }
          csoundSpinUnLock(lock);
          break;
        }

        case pb::PortDescription::KRATE_CONTROL: {
          MYFLT* channel_ptr = _channel_ptr[port_idx];
          int *lock = _channel_lock[port_idx];
          csoundSpinLock(lock);
          *channel_ptr = 0.0;
          csoundSpinUnLock(lock);
          break;
        }

        default:
          return ERROR_STATUS("Port %s has unsupported type %d", port.name.c_str(), port.type);
        }
      }
    }

    int rc;
    {
      RTUnsafe rtu;  // csound might do RT unsafe stuff internally.
      rc = csoundPerformKsmps(_csnd);
    }
    if (rc < 0) {
      return ERROR_STATUS("Csound performance failed (code %d)", rc);
    }

    // Copy channel data from Csound into output ports.
    for (size_t port_idx = 0 ; port_idx < _ports.size() ; ++port_idx) {
      const auto& port = _ports[port_idx];
      if (port.direction == pb::PortDescription::OUTPUT) {
        switch (port.type) {
        case pb::PortDescription::AUDIO:
        case pb::PortDescription::ARATE_CONTROL: {
          float* buf = (float*)buffers[port_idx];
          buf += pos;

          MYFLT* channel_ptr = _channel_ptr[port_idx];
          int *lock = _channel_lock[port_idx];
          csoundSpinLock(lock);
          for (uint32_t i = 0 ; i < ksmps ; ++i) {
            *buf++ = *channel_ptr++;
          }
          csoundSpinUnLock(lock);
          break;
        }

        case pb::PortDescription::KRATE_CONTROL: {
          float* buf = (float*)buffers[port_idx];

          MYFLT* channel_ptr = _channel_ptr[port_idx];
          int *lock = _channel_lock[port_idx];
          csoundSpinLock(lock);
          *buf = *channel_ptr;
          csoundSpinUnLock(lock);
          break;
        }

        default:
          return ERROR_STATUS("Port %s has unsupported type %d", port.name.c_str(), port.type);
        }
      }
    }

    pos += ksmps;
  }

  assert(pos == _host_system->block_size());

  return Status::Ok();
}

}
