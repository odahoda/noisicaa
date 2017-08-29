#include "processor_csound.h"

#include <assert.h>
#include <stdint.h>
#include "misc.h"


namespace noisicaa {

ProcessorCSoundBase::Instance::Instance() {}

ProcessorCSoundBase::Instance::~Instance() {
  if (csnd) {
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

  rc = csoundCompileOrc(instance->csnd, orchestra.c_str());
  if (rc < 0) {
    return Status::Error(sprintf("Failed to compile Csound orchestra (code %d)", rc));
  }

  rc = csoundStart(instance->csnd);
  if (rc < 0) {
    return Status::Error(sprintf("Failed to start Csound (code %d)", rc));
  }

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

  for (uint32_t i = 0 ; i < spec->num_ports() ; ++i) {
    _buffers.push_back(nullptr);
  }

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

        // in_events = {}
        // for port in self.inputs.values():
        //     if isinstance(port, ports.EventInputPort):
        //         l = list(atom.Atom.wrap(urid.get_static_mapper(), <uint8_t*>(<buffers.Buffer>self.__buffers[port.name]).data).events)
        //         in_events[port.name] = (port.csound_instr, l)

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
	} else {
	  return Status::Error(sprintf(
	      "Port %s has unsupported type %d",
	      port.name().c_str(), port.type()));
	}
      }
    }

        //         elif isinstance(port, ports.EventInputPort):
        //             instr, pending_events = in_events[port.name]
        //             while (len(pending_events) > 0
        //                    and pending_events[0].frames < (
        //                        pos + ctxt.sample_pos + self.__csnd.ksmps)):
        //                 event = pending_events.pop(0)
        //                 midi = event.atom.data
        //                 if midi[0] & 0xf0 == 0x90:
        //                     self.__csnd.add_score_event(
        //                         'i %s.%d 0 -1 %d %d' % (
        //                             instr, midi[1], midi[1], midi[2]))

        //                 elif midi[0] & 0xf0 == 0x80:
        //                     self.__csnd.add_score_event(
        //                         'i -%s.%d 0 0 0' % (
        //                             instr, midi[1]))

        //                 else:
        //                     raise NotImplementedError(
        //                         "Event class %s not supported" % type(event).__name__)

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


ProcessorCSound::ProcessorCSound(HostData* host_data)
  : ProcessorCSoundBase(host_data) {}

ProcessorCSound::~ProcessorCSound() {}

Status ProcessorCSound::setup(const ProcessorSpec* spec) {
  Status status = ProcessorCSoundBase::setup(spec);
  if (status.is_error()) { return status; }

  string orchestra;
  status = get_string_parameter("csound_orchestra", &orchestra);
  if (status.is_error()) { return status; }

  string score;
  status = get_string_parameter("csound_score", &score);
  if (status.is_error()) { return status; }

  status = set_code(orchestra, score);
  if (status.is_error()) { return status; }

  return Status::Ok();
}

void ProcessorCSound::cleanup() {

  ProcessorCSoundBase::cleanup();
}

}
