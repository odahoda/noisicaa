#include <assert.h>
#include <stdint.h>
#include <string.h>
#include "noisicaa/core/perf_stats.h"
#include "noisicaa/audioproc/vm/host_data.h"
#include "noisicaa/audioproc/vm/processor_csound.h"

namespace noisicaa {

ProcessorCSoundBase::Instance::Instance() {}

ProcessorCSoundBase::Instance::~Instance() {
  if (csnd != nullptr) {
    csoundDestroy(csnd);
  }
}

ProcessorCSoundBase::ProcessorCSoundBase(const char* logger_name, HostData* host_data)
  : Processor(logger_name, host_data),
    _next_instance(nullptr),
    _current_instance(nullptr),
    _old_instance(nullptr) {}

ProcessorCSoundBase::~ProcessorCSoundBase() {}

void ProcessorCSoundBase::_log_cb(CSOUND* csnd, int attr, const char* fmt, va_list args) {
  ProcessorCSoundBase* proc = (ProcessorCSoundBase*)csoundGetHostData(csnd);
  assert(proc != nullptr);
  proc->_log_cb(attr, fmt, args);
}

void ProcessorCSoundBase::_log_cb(int attr, const char* fmt, va_list args) {
  LogLevel level;
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

Status ProcessorCSoundBase::set_code(const string& orchestra, const string& score) {
  // Discard any next instance, which hasn't been picked up by the audio thread.
  Instance* prev_next_instance = _next_instance.exchange(nullptr);
  if (prev_next_instance != nullptr) {
    delete prev_next_instance;
  }

  // Discard instance, which the audio thread doesn't use anymore.
  Instance* old_instance = _old_instance.exchange(nullptr);
  if (old_instance != nullptr) {
    delete old_instance;
  }

  // Create the next instance.
  unique_ptr<Instance> instance(new Instance());
  instance->csnd = csoundCreate(this);
  if (instance->csnd == nullptr) {
    return Status::Error("Failed to create Csound instance.");
  }

  csoundSetMessageCallback(instance->csnd, ProcessorCSoundBase::_log_cb);

  int rc = csoundSetOption(instance->csnd, "-n");
  if (rc < 0) {
    return Status::Error("Failed to set Csound options (code %d)", rc);
  }

  _logger->info("csound orchestra:\n%s", orchestra.c_str());
  rc = csoundCompileOrc(instance->csnd, orchestra.c_str());
  if (rc < 0) {
    return Status::Error("Failed to compile Csound orchestra (code %d)", rc);
  }

  double zerodbfs = csoundGet0dBFS(instance->csnd);
  if (zerodbfs != 1.0) {
    return Status::Error("Csound orchestra must set 0dbfs=1.0 (found %f)", zerodbfs);
  }

  rc = csoundStart(instance->csnd);
  if (rc < 0) {
    return Status::Error("Failed to start Csound (code %d)", rc);
  }

  _logger->info("csound score:\n%s", score.c_str());
  rc = csoundReadScore(instance->csnd, score.c_str());
  if (rc < 0) {
    return Status::Error("Failed to read Csound score (code %d)", rc);
  }

  instance->channel_ptr.resize(_spec->num_ports());
  instance->channel_lock.resize(_spec->num_ports());
  for (uint32_t port_idx = 0 ; port_idx < _spec->num_ports() ; ++port_idx) {
    const auto& port = _spec->get_port(port_idx);

    if (port.type() == PortType::atomData) {
      continue;
    }

    MYFLT* channel_ptr;
    int type = csoundGetChannelPtr(
	instance->csnd, &channel_ptr, port.name().c_str(), 0);
    if (type < 0) {
      return Status::Error("Orchestra does not define the channel '%s'", port.name().c_str());
    }

    if (port.direction() == PortDirection::Output
	&& !(type & CSOUND_OUTPUT_CHANNEL)) {
      return Status::Error("Channel '%s' is not an output channel", port.name().c_str());
    }

    if (port.direction() == PortDirection::Input
	&& !(type & CSOUND_INPUT_CHANNEL)) {
      return Status::Error("Channel '%s' is not an input channel", port.name().c_str());
    }

    if (port.type() == PortType::audio	|| port.type() == PortType::aRateControl) {
      if ((type & CSOUND_CHANNEL_TYPE_MASK) != CSOUND_AUDIO_CHANNEL) {
	return Status::Error("Channel '%s' is not an audio channel", port.name().c_str());
      }
    } else if (port.type() == PortType::kRateControl) {
      if ((type & CSOUND_CHANNEL_TYPE_MASK) != CSOUND_CONTROL_CHANNEL) {
	return Status::Error("Channel '%s' is not an control channel", port.name().c_str());
      }
    } else {
      return Status::Error("Internal error, channel '%s' type %d", port.name().c_str(), port.type());
    }

    int rc = csoundGetChannelPtr(
	instance->csnd, &channel_ptr, port.name().c_str(), type);
    if (rc < 0) {
      return Status::Error("Failed to get channel pointer for port '%s'", port.name().c_str());
    }
    assert(channel_ptr != nullptr);

    instance->channel_ptr[port_idx] = channel_ptr;
    instance->channel_lock[port_idx] = csoundGetChannelLock(
	instance->csnd, port.name().c_str());
  }

  prev_next_instance = _next_instance.exchange(instance.release());
  assert(prev_next_instance == nullptr);

  return Status::Ok();
}

Status ProcessorCSoundBase::setup(const ProcessorSpec* spec) {
  Status status = Processor::setup(spec);
  if (status.is_error()) { return status; }

  memset(_log_buf, 0, sizeof(_log_buf));
  _buffers.resize(spec->num_ports());
  _event_input_ports.resize(spec->num_ports());

  return Status::Ok();
}

void ProcessorCSoundBase::cleanup() {
  Instance* instance = _next_instance.exchange(nullptr);
  if (instance != nullptr) {
    delete instance;
  }
  instance = _current_instance.exchange(nullptr);
  if (instance != nullptr) {
    delete instance;
  }
  instance = _old_instance.exchange(nullptr);
  if (instance != nullptr) {
    delete instance;
  }

  _buffers.clear();
  _event_input_ports.clear();

  Processor::cleanup();
}

Status ProcessorCSoundBase::connect_port(uint32_t port_idx, BufferPtr buf) {
  if (port_idx >= _buffers.size()) {
    return Status::Error("Invalid port index %d", port_idx);
  }
  _buffers[port_idx] = buf;
  return Status::Ok();
}

Status ProcessorCSoundBase::run(BlockContext* ctxt) {
  PerfTracker tracker(ctxt->perf.get(), "csound");

  for (uint32_t port_idx = 0 ; port_idx < _buffers.size() ; ++port_idx) {
    if (_buffers[port_idx] == nullptr) {
      return Status::Error("Port %d not connected.", port_idx);
    }
  }

  // If there is a next instance, make it the current. The current instance becomes
  // the old instance, which will eventually be destroyed in the main thread.
  // It must not happen that a next instance is available, before an old one has
  // been disposed of.
  Instance* instance = _next_instance.exchange(nullptr);
  if (instance != nullptr) {
    Instance* old_instance = _current_instance.exchange(instance);
    old_instance = _old_instance.exchange(old_instance);
    assert(old_instance == nullptr);
  }

  instance = _current_instance.load();
  if (instance == nullptr) {
    // No instance yet, just clear my output ports.
    for (uint32_t port_idx = 0 ; port_idx < _spec->num_ports() ; ++port_idx) {
      const auto& port = _spec->get_port(port_idx);
      if (port.direction() == PortDirection::Output) {
	if (port.type() == PortType::audio
	    || port.type() == PortType::aRateControl) {
	  float* buf = (float*)_buffers[port_idx];
	  for (uint32_t i = 0 ; i < ctxt->block_size ; ++i) {
	    *buf++ = 0.0;
	  }
	} else if (port.type() == PortType::kRateControl) {
	  float* buf = (float*)_buffers[port_idx];
	  *buf = 0.0;
	} else {
	  return Status::Error("Port %d has unsupported type %d", port_idx, port.type());
	}
      }
    }

    return Status::Ok();
  }

  for (uint32_t port_idx = 0 ; port_idx < _spec->num_ports() ; ++port_idx) {
    const auto& port = _spec->get_port(port_idx);
    if (port.direction() == PortDirection::Input
	&& port.type() == PortType::atomData) {
      LV2_Atom_Sequence* seq = (LV2_Atom_Sequence*)_buffers[port_idx];
      if (seq->atom.type != _host_data->lv2->urid.atom_sequence) {
	return Status::Error(
	    "Excepted sequence in port '%s', got %d.", port.name().c_str(), seq->atom.type);
      }
      LV2_Atom_Event* event = lv2_atom_sequence_begin(&seq->body);
      int instr = 1; // TODO: use port.csound_instr
      _event_input_ports[port_idx] = {seq, event, instr};
    }
  }

  uint32_t pos = 0;
  uint32_t ksmps = csoundGetKsmps(instance->csnd);
  while (pos < ctxt->block_size) {
    // Copy input ports into Csound channels.
    for (uint32_t port_idx = 0 ; port_idx < _spec->num_ports() ; ++port_idx) {
      const auto& port = _spec->get_port(port_idx);
      if (port.direction() == PortDirection::Input) {
	if (port.type() == PortType::audio
	    || port.type() == PortType::aRateControl) {
	  float* buf = (float*)_buffers[port_idx];
	  buf += pos;

	  MYFLT* channel_ptr = instance->channel_ptr[port_idx];
	  int *lock = instance->channel_lock[port_idx];
	  csoundSpinLock(lock);
	  for (uint32_t i = 0 ; i < ksmps ; ++i) {
	    *channel_ptr++ = *buf++;
	  }
	  csoundSpinUnLock(lock);
	} else if (port.type() == PortType::kRateControl) {
	  float* buf = (float*)_buffers[port_idx];

	  MYFLT* channel_ptr = instance->channel_ptr[port_idx];
	  int *lock = instance->channel_lock[port_idx];
	  csoundSpinLock(lock);
	  *channel_ptr = *buf;
	  csoundSpinUnLock(lock);
	} else if (port.type() == PortType::atomData) {
	  EventInputPort &ep = _event_input_ports[port_idx];

	  // TODO: is instrument started with one ksmps delay? needs further testing.
	  while (!lv2_atom_sequence_is_end(
	             &ep.seq->body, ep.seq->atom.size, ep.event)
		 && ep.event->time.frames < pos + ksmps) {
	    LV2_Atom& atom = ep.event->body;
	    if (atom.type == _host_data->lv2->urid.midi_event) {
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
		int rc = csoundScoreEvent(instance->csnd, 'i', p, 5);
		if (rc < 0) {
		  return Status::Error("csoundReadScore failed (code %d).", rc);
		}
	      } else if ((midi[0] & 0xf0) == 0x80) {
		MYFLT p[3] = {
		  /* p1: instr    */ -((MYFLT)ep.instr + (MYFLT)midi[1] / 1000.0),
		  /* p2: time     */ 0.0,
		  /* p3: duration */ 0.0,
		};
		//_logger->info("i %f %f %f", p[0], p[1], p[2]);
		int rc = csoundScoreEvent(instance->csnd, 'i', p, 3);
		if (rc < 0) {
		  return Status::Error("csoundReadScore failed (code %d).", rc);
		}
	      } else {
		_logger->warning("Ignoring unsupported midi event %d.", midi[0] & 0xf0);
	      }
	    } else {
	      _logger->warning("Ignoring event %d in sequence.", atom.type);
	    }
	    ep.event = lv2_atom_sequence_next(ep.event);
	  }
	} else {
	  return Status::Error("Port %s has unsupported type %d", port.name().c_str(), port.type());
	}
      } else {
	assert(port.direction() == PortDirection::Output);

	if (port.type() == PortType::audio
	    || port.type() == PortType::aRateControl) {
	  MYFLT* channel_ptr = instance->channel_ptr[port_idx];
	  int *lock = instance->channel_lock[port_idx];
	  csoundSpinLock(lock);
	  for (uint32_t i = 0 ; i < ksmps ; ++i) {
	    *channel_ptr++ = 0.0;
	  }
	  csoundSpinUnLock(lock);
	} else if (port.type() == PortType::kRateControl) {
	  MYFLT* channel_ptr = instance->channel_ptr[port_idx];
	  int *lock = instance->channel_lock[port_idx];
	  csoundSpinLock(lock);
	  *channel_ptr = 0.0;
	  csoundSpinUnLock(lock);
	} else {
	  return Status::Error("Port %s has unsupported type %d", port.name().c_str(), port.type());
	}
      }
    }

    int rc = csoundPerformKsmps(instance->csnd);
    if (rc < 0) {
      return Status::Error("Csound performance failed (code %d)", rc);
    }

    // Copy channel data from Csound into output ports.
    for (uint32_t port_idx = 0 ; port_idx < _spec->num_ports() ; ++port_idx) {
      const auto& port = _spec->get_port(port_idx);
      if (port.direction() == PortDirection::Output) {
	if (port.type() == PortType::audio
	    || port.type() == PortType::aRateControl) {
	  float* buf = (float*)_buffers[port_idx];
	  buf += pos;

	  MYFLT* channel_ptr = instance->channel_ptr[port_idx];
	  int *lock = instance->channel_lock[port_idx];
	  csoundSpinLock(lock);
	  for (uint32_t i = 0 ; i < ksmps ; ++i) {
	    *buf++ = *channel_ptr++;
	  }
	  csoundSpinUnLock(lock);
	} else if (port.type() == PortType::kRateControl) {
	  float* buf = (float*)_buffers[port_idx];

	  MYFLT* channel_ptr = instance->channel_ptr[port_idx];
	  int *lock = instance->channel_lock[port_idx];
	  csoundSpinLock(lock);
	  *buf = *channel_ptr;
	  csoundSpinUnLock(lock);
	} else {
	  return Status::Error("Port %s has unsupported type %d", port.name().c_str(), port.type());
	}
      }
    }

    pos += ksmps;
  }

  assert(pos == ctxt->block_size);

  return Status::Ok();
}

}
