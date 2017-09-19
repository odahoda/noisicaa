#include <assert.h>
#include <stdint.h>
#include "noisicaa/core/perf_stats.h"
#include "noisicore/host_data.h"
#include "noisicore/misc.h"
#include "noisicore/processor_csound.h"

namespace {

using namespace std;

string port_name_to_csound_label(const string &port_name) {
  string result;
  bool was_alpha = false;
  for (const auto& c : port_name) {
    bool is_alpha = isalpha(c);
    if (is_alpha && !was_alpha) {
      result += toupper(c);
    } else if (is_alpha) {
      result += c;
    }
    was_alpha = is_alpha;
  }

  // name.title().replace(':', '')
  return result;
}

}  // namespace

namespace noisicaa {

ProcessorCSoundBase::Instance::Instance() {}

ProcessorCSoundBase::Instance::~Instance() {
  if (csnd != nullptr) {
    csoundDestroy(csnd);
  }
}

ProcessorCSoundBase::ProcessorCSoundBase(HostData* host_data)
  : Processor(host_data),
    _next_instance(nullptr),
    _current_instance(nullptr),
    _old_instance(nullptr) {}

ProcessorCSoundBase::~ProcessorCSoundBase() {}

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
  instance->csnd = csoundCreate(nullptr);
  if (instance->csnd == nullptr) {
    return Status::Error("Failed to create Csound instance.");
  }

  int rc = csoundSetOption(instance->csnd, "-n");
  if (rc < 0) {
    return Status::Error(sprintf("Failed to set Csound options (code %d)", rc));
  }

  log(LogLevel::INFO, "csound orchestra:\n%s", orchestra.c_str());
  rc = csoundCompileOrc(instance->csnd, orchestra.c_str());
  if (rc < 0) {
    return Status::Error(sprintf("Failed to compile Csound orchestra (code %d)", rc));
  }

  rc = csoundStart(instance->csnd);
  if (rc < 0) {
    return Status::Error(sprintf("Failed to start Csound (code %d)", rc));
  }

  log(LogLevel::INFO, "csound score:\n%s", score.c_str());
  rc = csoundReadScore(instance->csnd, score.c_str());
  if (rc < 0) {
    return Status::Error(sprintf("Failed to read Csound score (code %d)", rc));
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
      return Status::Error(
	   sprintf("Orchestra does not define the channel '%s'",
		   port.name().c_str()));
    }

    if (port.direction() == PortDirection::Output
	&& !(type & CSOUND_OUTPUT_CHANNEL)) {
      return Status::Error(
	   sprintf("Channel '%s' is not an output channel", port.name().c_str()));
    }

    if (port.direction() == PortDirection::Input
	&& !(type & CSOUND_INPUT_CHANNEL)) {
      return Status::Error(
	   sprintf("Channel '%s' is not an input channel", port.name().c_str()));
    }

    if (port.type() == PortType::audio	|| port.type() == PortType::aRateControl) {
      if ((type & CSOUND_CHANNEL_TYPE_MASK) != CSOUND_AUDIO_CHANNEL) {
	return Status::Error(
	    sprintf("Channel '%s' is not an audio channel", port.name().c_str()));
      }
    } else if (port.type() == PortType::kRateControl) {
      if ((type & CSOUND_CHANNEL_TYPE_MASK) != CSOUND_CONTROL_CHANNEL) {
	return Status::Error(
	    sprintf("Channel '%s' is not an control channel", port.name().c_str()));
      }
    } else {
      return Status::Error(
	  sprintf("Internal error, channel '%s' type %d",
		  port.name().c_str(), port.type()));
    }

    int rc = csoundGetChannelPtr(
	instance->csnd, &channel_ptr, port.name().c_str(), type);
    if (rc < 0) {
      return Status::Error(
	   sprintf("Failed to get channel pointer for port '%s'",
		   port.name().c_str()));
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
    return Status::Error(sprintf("Invalid port index %d", port_idx));
  }
  _buffers[port_idx] = buf;
  return Status::Ok();
}

Status ProcessorCSoundBase::run(BlockContext* ctxt) {
  PerfTracker tracker(ctxt->perf.get(), "csound");

  for (uint32_t port_idx = 0 ; port_idx < _buffers.size() ; ++port_idx) {
    if (_buffers[port_idx] == nullptr) {
      return Status::Error(sprintf("Port %d not connected.", port_idx));
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
	  return Status::Error(
	       sprintf("Port %d has unsupported type %d", port_idx, port.type()));
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
            sprintf("Excepted sequence in port '%s', got %d.",
		    port.name().c_str(), seq->atom.type));
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
		// note on
		char buf[80];
		snprintf(
		    buf, sizeof(buf),
		    "i %d.%d 0 -1 %d %d", ep.instr, midi[1], midi[1], midi[2]);
		int rc = csoundReadScore(instance->csnd, buf);
		if (rc < 0) {
		  return Status::Error(sprintf(
		      "csoundReadScore failed (code %d).", rc));
		}
	      } else if ((midi[0] & 0xf0) == 0x80) {
		// note off
		char buf[80];
		snprintf(buf, sizeof(buf), "i -%d.%d 0 0 0", ep.instr, midi[1]);
		int rc = csoundReadScore(instance->csnd, buf);
		if (rc < 0) {
		  return Status::Error(sprintf(
		      "csoundReadScore failed (code %d).", rc));
		}
	      } else {
		log(LogLevel::WARNING, "Ignoring unsupported midi event %d.", midi[0] & 0xf0);
	      }
	    } else {
	      log(LogLevel::WARNING, "Ignoring event %d in sequence.", atom.type);
	    }
	    ep.event = lv2_atom_sequence_next(ep.event);
	  }
	} else {
	  return Status::Error(sprintf(
	      "Port %s has unsupported type %d",
	      port.name().c_str(), port.type()));
	}
      }
    }

        //     for parameter in self.description.parameters:
        //         if parameter.param_type == node_db.ParameterType.Float:
        //             self.__csnd.set_control_channel_value(
        //                 parameter.name, self.get_param(parameter.name))

    int rc = csoundPerformKsmps(instance->csnd);
    if (rc < 0) {
      return Status::Error(sprintf("Csound performance failed (code %d)", rc));
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
	  return Status::Error(sprintf(
	      "Port %s has unsupported type %d",
	      port.name().c_str(), port.type()));
	}
      }
    }

    pos += ksmps;
  }

  assert(pos == ctxt->block_size);

  return Status::Ok();
}

ProcessorCSound::ProcessorCSound(HostData *host_data)
  : ProcessorCSoundBase(host_data) {}

Status ProcessorCSound::setup(const ProcessorSpec* spec) {
  Status status = ProcessorCSoundBase::setup(spec);
  if (status.is_error()) { return status; }

  StatusOr<string> stor_orchestra = get_string_parameter("csound_orchestra");
  if (stor_orchestra.is_error()) { return stor_orchestra; }
  string orchestra = stor_orchestra.result();

  StatusOr<string> stor_score = get_string_parameter("csound_score");
  if (stor_score.is_error()) { return stor_score; }
  string score = stor_score.result();

  status = set_code(orchestra, score);
  if (status.is_error()) { return status; }

  return Status::Ok();
}

void ProcessorCSound::cleanup() {
  ProcessorCSoundBase::cleanup();
}


ProcessorCustomCSound::ProcessorCustomCSound(HostData *host_data)
  : ProcessorCSoundBase(host_data) {}

Status ProcessorCustomCSound::setup(const ProcessorSpec* spec) {
  Status status = ProcessorCSoundBase::setup(spec);
  if (status.is_error()) { return status; }

  StatusOr<string> stor_orchestra = get_string_parameter("csound_orchestra");
  if (stor_orchestra.is_error()) { return stor_orchestra; }
  string orchestra = stor_orchestra.result();

  StatusOr<string> stor_score = get_string_parameter("csound_score");
  if (stor_score.is_error()) { return stor_score; }
  string score = stor_score.result();

  string orchestra_preamble = "ksmps=32\nnchnls=2\n";

  for (uint32_t i = 0 ; i < _spec->num_ports() ; ++i) {
    const auto& port_spec = _spec->get_port(i);

    if (port_spec.type() == PortType::audio
	&& port_spec.direction() == PortDirection::Input) {
      orchestra_preamble += sprintf(
	  "ga%s chnexport \"%s\", 1\n",
	  port_name_to_csound_label(port_spec.name()).c_str(),
	  port_spec.name().c_str());
    } else if (port_spec.type() == PortType::audio
	       && port_spec.direction() == PortDirection::Output) {
      orchestra_preamble += sprintf(
	  "ga%s chnexport \"%s\", 2\n",
	  port_name_to_csound_label(port_spec.name()).c_str(),
	  port_spec.name().c_str());
    } else if (port_spec.type() == PortType::aRateControl
	       && port_spec.direction() == PortDirection::Input) {
      orchestra_preamble += sprintf(
	  "ga%s chnexport \"%s\", 1\n",
	  port_name_to_csound_label(port_spec.name()).c_str(),
	  port_spec.name().c_str());
    } else if (port_spec.type() == PortType::aRateControl
	       && port_spec.direction() == PortDirection::Output) {
      orchestra_preamble += sprintf(
	  "ga%s chnexport \"%s\", 2\n",
	  port_name_to_csound_label(port_spec.name()).c_str(),
	  port_spec.name().c_str());
    } else if (port_spec.type() == PortType::atomData
	       && port_spec.direction() == PortDirection::Input) {
    } else {
      return Status::Error(sprintf("Port %s not supported", port_spec.name().c_str()));
    }
  }

  status = set_code(orchestra_preamble + orchestra, score);
  if (status.is_error()) { return status; }

  return Status::Ok();
}

void ProcessorCustomCSound::cleanup() {
  ProcessorCSoundBase::cleanup();
}

}
