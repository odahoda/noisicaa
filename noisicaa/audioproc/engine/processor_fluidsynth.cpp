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

#include "noisicaa/core/perf_stats.h"
#include "noisicaa/audioproc/engine/processor_fluidsynth.h"
#include "noisicaa/host_system/host_system.h"

namespace noisicaa {

ProcessorFluidSynth::ProcessorFluidSynth(
    const string& node_id, HostSystem* host_system, const pb::NodeDescription& desc)
  : Processor(node_id, "noisicaa.audioproc.engine.processor.fluidsynth", host_system, desc) {}

ProcessorFluidSynth::~ProcessorFluidSynth() {}

Status ProcessorFluidSynth::setup_internal() {
  RETURN_IF_ERROR(Processor::setup_internal());

  if (!_desc.has_fluidsynth()) {
    return ERROR_STATUS("NodeDescription misses fluidsynth field.");
  }

  const pb::FluidSynthDescription& fluid_desc = _desc.fluidsynth();

  _logger->info(
      "Setting up fluidsynth processor for %s, bank=%d, preset=%d",
      fluid_desc.soundfont_path().c_str(), fluid_desc.bank(), fluid_desc.preset());

  _settings = new_fluid_settings();
  if (_settings == nullptr) {
    return ERROR_STATUS("Failed to create fluid settings object.");
  }

  int rc = fluid_settings_setnum(_settings, "synth.gain", 0.5);
  if (rc == FLUID_FAILED) {
    // TODO: error message?
    return ERROR_STATUS("Failed to set synth.gain setting.");
  }

  rc = fluid_settings_setnum(_settings, "synth.sample-rate", _host_system->sample_rate());
  if (rc == FLUID_FAILED) {
    // TODO: error message?
    return ERROR_STATUS("Failed to set synth.sample-rate setting.");
  }

  _synth = new_fluid_synth(_settings);
  if (_synth == nullptr) {
    return ERROR_STATUS("Failed to create fluid synth object.");
  }

  int sfid = fluid_synth_sfload(_synth, fluid_desc.soundfont_path().c_str(), true);
  if (sfid == FLUID_FAILED) {
    // TODO: error message?
    return ERROR_STATUS("Failed to load soundfont.");
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
    return ERROR_STATUS("System reset failed.");
  }

  rc = fluid_synth_program_select(_synth, 0, sfid, fluid_desc.bank(), fluid_desc.preset());
  if (rc == FLUID_FAILED) {
    // TODO: error message?
    return ERROR_STATUS("Program select failed.");
  }

  return Status::Ok();
}

void ProcessorFluidSynth::cleanup_internal() {
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

  Processor::cleanup_internal();
}

Status ProcessorFluidSynth::connect_port_internal(
    BlockContext* ctxt, uint32_t port_idx, BufferPtr buf) {
  assert(port_idx < 3);
  _buffers[port_idx] = buf;
  return Status::Ok();
}

Status ProcessorFluidSynth::process_block_internal(BlockContext* ctxt, TimeMapper* time_mapper) {
  PerfTracker tracker(ctxt->perf.get(), "fluidsynth");

  LV2_Atom_Sequence* seq = (LV2_Atom_Sequence*)_buffers[0];
  if (seq->atom.type != _host_system->lv2->urid.atom_sequence) {
    return ERROR_STATUS("Excepted sequence in port 'in', got %d.", seq->atom.type);
  }
  LV2_Atom_Event* event = lv2_atom_sequence_begin(&seq->body);

  uint32_t segment_start = 0;
  float* out_left = (float*)_buffers[1];
  float* out_right = (float*)_buffers[2];
  while (!lv2_atom_sequence_is_end(&seq->body, seq->atom.size, event)) {
    if (event->body.type == _host_system->lv2->urid.midi_event) {
      uint32_t esample_pos;

      if (event->time.frames != -1) {
        if (event->time.frames < 0 || event->time.frames >= _host_system->block_size()) {
          return ERROR_STATUS(
               "Event timestamp %d out of bounds [0,%d]", event->time.frames, _host_system->block_size());
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
          return ERROR_STATUS("Failed to render samples");
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

  if (segment_start < _host_system->block_size()) {
    uint32_t num_samples = _host_system->block_size() - segment_start;
    float *lmap[1] = { out_left };
    float *rmap[1] = { out_right };
    int rc = fluid_synth_nwrite_float(_synth, num_samples, lmap, rmap, nullptr, nullptr);
    if (rc == FLUID_FAILED) {
      // TODO: error message
      return ERROR_STATUS("Failed to render samples");
    }
  }

  return Status::Ok();
}

}
