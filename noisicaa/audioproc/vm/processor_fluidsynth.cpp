#include "noisicaa/core/perf_stats.h"
#include "noisicaa/audioproc/vm/processor_fluidsynth.h"
#include "noisicaa/audioproc/vm/host_data.h"

namespace noisicaa {

ProcessorFluidSynth::ProcessorFluidSynth(const string& node_id, HostData* host_data)
  : Processor(node_id, "noisicaa.audioproc.vm.processor.fluidsynth", host_data) {}

ProcessorFluidSynth::~ProcessorFluidSynth() {}

Status ProcessorFluidSynth::setup(const ProcessorSpec* spec) {
  Status status = Processor::setup(spec);
  if (status.is_error()) { return status; }

  StatusOr<string> stor_soundfont_path = get_string_parameter("soundfont_path");
  if (stor_soundfont_path.is_error()) { return stor_soundfont_path; }
  string soundfont_path = stor_soundfont_path.result();

  StatusOr<int64_t> stor_bank = get_int_parameter("bank");
  if (stor_bank.is_error()) { return stor_bank; }
  int64_t bank = stor_bank.result();

  StatusOr<int64_t> stor_preset = get_int_parameter("preset");
  if (stor_preset.is_error()) { return stor_preset; }
  int64_t preset = stor_preset.result();

  _logger->info("Setting up fluidsynth processor for %s, bank=%d, preset=%d",
      soundfont_path.c_str(), bank, preset);

  _settings = new_fluid_settings();
  if (_settings == nullptr) {
    return Status::Error("Failed to create fluid settings object.");
  }

  int rc = fluid_settings_setnum(_settings, "synth.gain", 0.5);
  if (rc == FLUID_FAILED) {
    // TODO: error message?
    return Status::Error("Failed to set synth.gain setting.");
  }

  // TODO: get from pipeline
  rc = fluid_settings_setnum(_settings, "synth.sample-rate", 44100);
  if (rc == FLUID_FAILED) {
    // TODO: error message?
    return Status::Error("Failed to set synth.sample-rate setting.");
  }

  _synth = new_fluid_synth(_settings);
  if (_synth == nullptr) {
    return Status::Error("Failed to create fluid synth object.");
  }

  int sfid = fluid_synth_sfload(_synth, soundfont_path.c_str(), true);
  if (sfid == FLUID_FAILED) {
    // TODO: error message?
    return Status::Error("Failed to load soundfont.");
  }

  // try:
  //     sfont = self.master_sfonts[self.__soundfont_path]
  // except KeyError:
  //     logger.info(
  //         "Adding new soundfont %s to master synth.",
  //         self.__soundfont_path)
  //     master_sfid = self.master_synth.sfload(self.__soundfont_path)
  //     sfont = self.master_synth.get_sfont(master_sfid)
  //     self.master_sfonts[self.__soundfont_path] = sfont

  // logger.debug("Using soundfont %s", sfont.id)
  // sfid = self.__synth.add_sfont(sfont)

  // logger.debug("Soundfont id=%s", sfid)
  // self.__sfont = sfont

  rc = fluid_synth_system_reset(_synth);
  if (rc == FLUID_FAILED) {
    // TODO: error message?
    return Status::Error("System reset failed.");
  }

  rc = fluid_synth_program_select(_synth, 0, sfid, bank, preset);
  if (rc == FLUID_FAILED) {
    // TODO: error message?
    return Status::Error("Program select failed.");
  }

  return Status::Ok();
}

void ProcessorFluidSynth::cleanup() {
  if (_synth != nullptr) {
        //     self.__synth.system_reset()
        //     if self.__sfont is not None:
        //         # TODO: This call spits out a ton of "CRITICAL **:
        //         # fluid_synth_sfont_unref: assertion 'sfont_info != NULL' failed"
        //         # messages on STDERR
        //         self.__synth.remove_sfont(self.__sfont)
        //         self.__sfont = None

    delete_fluid_synth(_synth);
    _synth = nullptr;
  }

  if (_settings != nullptr) {
    delete_fluid_settings(_settings);
    _settings = nullptr;
  }

  Processor::cleanup();
}

Status ProcessorFluidSynth::connect_port(uint32_t port_idx, BufferPtr buf) {
  assert(port_idx < 3);
  _buffers[port_idx] = buf;
  return Status::Ok();
}

Status ProcessorFluidSynth::run(BlockContext* ctxt) {
  PerfTracker tracker(ctxt->perf.get(), "fluidsynth");

  LV2_Atom_Sequence* seq = (LV2_Atom_Sequence*)_buffers[0];
  if (seq->atom.type != _host_data->lv2->urid.atom_sequence) {
    return Status::Error("Excepted sequence in port 'in', got %d.", seq->atom.type);
  }
  LV2_Atom_Event* event = lv2_atom_sequence_begin(&seq->body);

  uint32_t segment_start = 0;
  float* out_left = (float*)_buffers[1];
  float* out_right = (float*)_buffers[2];
  while (!lv2_atom_sequence_is_end(&seq->body, seq->atom.size, event)) {
    if (event->body.type == _host_data->lv2->urid.midi_event) {
      uint32_t esample_pos;

      if (event->time.frames != -1) {
	if (event->time.frames < 0 || event->time.frames >= ctxt->block_size) {
	  return Status::Error(
	       "Event timestamp %d out of bounds [0,%d]", event->time.frames, ctxt->block_size);
	}

	esample_pos = event->time.frames;
      } else {
	esample_pos = 0;
      }

      if (esample_pos > segment_start) {
	uint32_t num_samples = esample_pos - segment_start;
	float *lmap[1] = { out_left };
	float *rmap[1] = { out_right };
	int rc = fluid_synth_nwrite_float(_synth, num_samples, lmap, rmap, nullptr, nullptr);
	if (rc == FLUID_FAILED) {
	  // TODO: error message
	  return Status::Error("Failed to render samples");
	}

	segment_start = esample_pos;
	out_left += num_samples;
	out_right += num_samples;
      }

      uint8_t* midi = (uint8_t*)LV2_ATOM_CONTENTS(LV2_Atom, &event->body);
      if ((midi[0] & 0xf0) == 0x90) {
	int rc = fluid_synth_noteon(_synth, 0, midi[1], midi[2]);
	if (rc == FLUID_FAILED) {
	  _logger->warning("noteon failed.");
	}
      } else if ((midi[0] & 0xf0) == 0x80) {
	int rc = fluid_synth_noteoff(_synth, 0, midi[1]);
	if (rc == FLUID_FAILED) {
	  _logger->warning("noteoff failed.");
	}
      } else {
	_logger->warning("Ignoring unsupported midi event %d.", midi[0] & 0xf0);
      }
    } else {
      _logger->warning("Ignoring event %d in sequence.", event->body.type);
    }

    event = lv2_atom_sequence_next(event);
  }

  if (segment_start < ctxt->block_size) {
    uint32_t num_samples = ctxt->block_size - segment_start;
    float *lmap[1] = { out_left };
    float *rmap[1] = { out_right };
    int rc = fluid_synth_nwrite_float(_synth, num_samples, lmap, rmap, nullptr, nullptr);
    if (rc == FLUID_FAILED) {
      // TODO: error message
      return Status::Error("Failed to render samples");
    }
  }

  return Status::Ok();
}

}
