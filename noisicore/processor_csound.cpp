#include "processor_csound.h"

#include <stdint.h>
#include "misc.h"


// TODO: assuming the channel pointers are constant for the lifetime of a
// Csound instance, create a vector of channel pointers and populate it
// in set_code(). _{next,current,old}_instance should point to a struct with
// the instance pointer and the vector for that instance's channel pointers.

namespace noisicaa {

ProcessorCSoundBase::ProcessorCSoundBase(HostData* host_data)
  : Processor(host_data),
    _next_instance(nullptr),
    _current_instance(nullptr),
    _old_instance(nullptr) {}

ProcessorCSoundBase::~ProcessorCSoundBase() {}

Status ProcessorCSoundBase::set_code(const string& orchestra, const string& score) {
  CSOUND* instance;

  // Discard any next instance, which hasn't been picked up by the audio thread.
  instance = _next_instance.exchange(nullptr);
  if (instance != nullptr) {
    csoundDestroy(instance);
  }

  // Discard instance, which the audio thread doesn't use anymore.
  instance = _old_instance.exchange(nullptr);
  if (instance != nullptr) {
    csoundDestroy(instance);
  }

  // Create the next instance.
  instance = csoundCreate(nullptr);
  if (instance == nullptr) {
    return Status::Error("Failed to create Csound instance.");
  }

  auto destroy_instance = scopeGuard([&]() {
      csoundDestroy(instance);
    });

  int rc = csoundSetOption(instance, "-n");
  if (rc < 0) {
    return Status::Error(sprintf("Failed to set Csound options (code %d)", rc));
  }

  rc = csoundCompileOrc(instance, orchestra.c_str());
  if (rc < 0) {
    return Status::Error(sprintf("Failed to compile Csound orchestra (code %d)", rc));
  }

  rc = csoundStart(instance);
  if (rc < 0) {
    return Status::Error(sprintf("Failed to start Csound (code %d)", rc));
  }

  rc = csoundReadScore(instance, score.c_str());
  if (rc < 0) {
    return Status::Error(sprintf("Failed to read Csound score (code %d)", rc));
  }

  destroy_instance.dismiss();
  instance = _next_instance.exchange(instance);
  assert(instance == nullptr);

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
  CSOUND* instance = _next_instance.exchange(nullptr);
  if (instance != nullptr) {
    csoundDestroy(instance);
  }
  instance = _current_instance.exchange(nullptr);
  if (instance != nullptr) {
    csoundDestroy(instance);
  }
  instance = _old_instance.exchange(nullptr);
  if (instance != nullptr) {
    csoundDestroy(instance);
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
  CSOUND* instance = _next_instance.exchange(nullptr);
  if (instance != nullptr) {
    CSOUND* old_instance = _current_instance.exchange(instance);
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
  uint32_t ksmps = csoundGetKsmps(instance);
  while (pos < ctxt->block_size) {
    for (uint32_t port_idx = 0 ; port_idx < _spec->num_ports() ; ++port_idx) {
      const auto& port = _spec->get_port(port_idx);
      if (port.direction() == PortDirection::Input) {
	if (port.type() == PortType::audio
	    || port.type() == PortType::aRateControl) {
	  MYFLT* channel_ptr;
	  int rc = csoundGetChannelPtr(
	      instance, &channel_ptr, port.name().c_str(),
	      CSOUND_AUDIO_CHANNEL | CSOUND_INPUT_CHANNEL);
	  if (rc < 0) {
	    return Status::Error(sprintf(
	        "Failed to get channel pointer for ort %s (code %d)",
	        port.name().c_str(), rc));
	  }

	  float* buf = (float*)_buffers[port_idx];
	  buf += pos;
	  for (uint32_t i = 0 ; i < ksmps ; ++i) {
	    *channel_ptr++ = *buf++;
	  }
	} else if (port.type() == PortType::kRateControl) {
	  MYFLT* channel_ptr;
	  int rc = csoundGetChannelPtr(
	      instance, &channel_ptr, port.name().c_str(),
	      CSOUND_CONTROL_CHANNEL | CSOUND_INPUT_CHANNEL);
	  if (rc < 0) {
	    return Status::Error(sprintf(
	        "Failed to get channel pointer for ort %s (code %d)",
	        port.name().c_str(), rc));
	  }

	  float* buf = (float*)_buffers[port_idx];
	  *channel_ptr = *buf;
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

    int rc = csoundPerformKsmps(instance);
    if (rc < 0) {
      return Status::Error(sprintf("Csound performance failed (code %d)", rc));
    }

    for (uint32_t port_idx = 0 ; port_idx < _spec->num_ports() ; ++port_idx) {
      const auto& port = _spec->get_port(port_idx);
      if (port.direction() == PortDirection::Output) {
	if (port.type() == PortType::audio
	    || port.type() == PortType::aRateControl) {
	  MYFLT* channel_ptr;
	  rc = csoundGetChannelPtr(
	      instance, &channel_ptr, port.name().c_str(),
	      CSOUND_AUDIO_CHANNEL | CSOUND_OUTPUT_CHANNEL);
	  if (rc < 0) {
	    return Status::Error(sprintf(
	        "Failed to get channel pointer for ort %s (code %d)",
	        port.name().c_str(), rc));
	  }

	  float* buf = (float*)_buffers[port_idx];
	  buf += pos;
	  for (uint32_t i = 0 ; i < ksmps ; ++i) {
	    *buf++ = *channel_ptr++;
	  }
	} else if (port.type() == PortType::kRateControl) {
	  MYFLT* channel_ptr;
	  rc = csoundGetChannelPtr(
	      instance, &channel_ptr, port.name().c_str(),
	      CSOUND_CONTROL_CHANNEL | CSOUND_OUTPUT_CHANNEL);
	  if (rc < 0) {
	    return Status::Error(sprintf(
	        "Failed to get channel pointer for ort %s (code %d)",
	        port.name().c_str(), rc));
	  }

	  float* buf = (float*)_buffers[port_idx];
	  *buf = *channel_ptr;
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
