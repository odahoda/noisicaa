/*
 * @begin:license
 *
 * Copyright (c) 2015-2019, Benjamin Niemann <pink@odahoda.de>
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

#include "noisicaa/audioproc/public/instrument_spec.pb.h"
#include "noisicaa/audioproc/public/processor_message.pb.h"
#include "noisicaa/audioproc/engine/misc.h"
#include "noisicaa/audioproc/engine/csound_util.h"
#include "noisicaa/audioproc/engine/fluidsynth_util.h"
#include "noisicaa/builtin_nodes/processor_message_registry.pb.h"
#include "noisicaa/builtin_nodes/instrument/processor.h"

namespace noisicaa {

ProcessorInstrument::ProcessorInstrument(
    const string& realm_name, const string& node_id, HostSystem *host_system,
    const pb::NodeDescription& desc)
  : Processor(
      realm_name, node_id, "noisicaa.audioproc.engine.processor.instrument", host_system, desc),
    _next_instrument(nullptr),
    _current_instrument(nullptr),
    _old_instrument(nullptr) {}

Status ProcessorInstrument::setup_internal() {
  RETURN_IF_ERROR(Processor::setup_internal());

  assert(_desc.ports_size() == 3);
  _buffers.resize(_desc.ports_size());

  return Status::Ok();
}

void ProcessorInstrument::cleanup_internal() {
  Instrument* instrument = _next_instrument.exchange(nullptr);
  if (instrument != nullptr) {
    delete instrument;
  }
  instrument = _current_instrument.exchange(nullptr);
  if (instrument != nullptr) {
    delete instrument;
  }
  instrument = _old_instrument.exchange(nullptr);
  if (instrument != nullptr) {
    delete instrument;
  }

  _buffers.clear();

  Processor::cleanup_internal();
}

Status ProcessorInstrument::handle_message_internal(pb::ProcessorMessage* msg) {
  if (msg->HasExtension(pb::change_instrument)) {
    unique_ptr<pb::ProcessorMessage> msg_ptr(msg);
    return change_instrument(msg->GetExtension(pb::change_instrument).instrument_spec());
  }

  return Processor::handle_message_internal(msg);
}

Status ProcessorInstrument::connect_port_internal(
    BlockContext* ctxt, uint32_t port_idx, BufferPtr buf) {
  if (port_idx >= _buffers.size()) {
    return ERROR_STATUS("Invalid port index %d", port_idx);
  }
  _buffers[port_idx] = buf;
  return Status::Ok();
}

Status ProcessorInstrument::process_block_internal(BlockContext* ctxt, TimeMapper* time_mapper) {
  // If there is a next instrument, make it the current. The current instrument becomes
  // the old instrument, which will eventually be destroyed in the main thread.
  // It must not happen that a next instrument is available, before an old one has
  // been disposed of.
  Instrument* instrument = _next_instrument.exchange(nullptr);
  if (instrument != nullptr) {
    Instrument* old_instrument = _current_instrument.exchange(instrument);
    old_instrument = _old_instrument.exchange(old_instrument);
    assert(old_instrument == nullptr);
  }

  instrument = _current_instrument.load();
  if (instrument == nullptr) {
    // No instrument yet, just clear my output ports.
    clear_all_outputs();
    return Status::Ok();
  }

  if (instrument->fluidsynth.get()) {
    FluidSynthUtil* fluidsynth = instrument->fluidsynth.get();
    RETURN_IF_ERROR(fluidsynth->process_block(ctxt, time_mapper, _buffers));
  } else if (instrument->csound.get()) {
    CSoundUtil* csound = instrument->csound.get();
    RETURN_IF_ERROR(csound->process_block(ctxt, time_mapper, _buffers));
  } else {
    clear_all_outputs();
  }
  return Status::Ok();
}

Status ProcessorInstrument::change_instrument(const pb::InstrumentSpec& spec) {
  _logger->info("Change instrument:\n%s", spec.DebugString().c_str());

  // Discard any next instrument, which hasn't been picked up by the audio thread.
  Instrument* prev_next_instrument = _next_instrument.exchange(nullptr);
  if (prev_next_instrument != nullptr) {
    delete prev_next_instrument;
  }

  // Discard instrument, which the audio thread doesn't use anymore.
  Instrument* old_instrument = _old_instrument.exchange(nullptr);
  if (old_instrument != nullptr) {
    delete old_instrument;
  }

  // Create the new instrument.
  unique_ptr<Instrument> instrument(new Instrument());

  if (spec.instrument_type_case() == pb::InstrumentSpec::kSample) {
    const auto& sample_spec = spec.sample();

    // TODO:
    // - get sample attributes using sndfile
    // - explicitly set table size, so loading is not deferred.
    string orchestra = R"---(
0dbfs = 1.0
ksmps = 32
nchnls = 2
gaOutL chnexport "out:left", 2
gaOutR chnexport "out:right", 2
instr 1
  iPitch = p4
  iVelocity = p5
  iFreq = cpsmidinn(iPitch)
  if (iVelocity == 0) then
    iAmp = 0.0
  else
    iAmp = 0.5 * db(-20 * log10(127^2 / iVelocity^2))
  endif
  iChannels = ftchnls(1)
  if (iChannels == 1) then
    aOut loscil3 iAmp, iFreq, 1, 261.626, 0
    gaOutL = gaOutL + aOut
    gaOutR = gaOutR + aOut
  elseif (iChannels == 2) then
    aOutL, aOutR loscil3 iAmp, iFreq, 1, 220, 0
    gaOutL = gaOutL + aOutL
    gaOutR = gaOutR + aOutR
  endif
endin
)---";

    string score = sprintf("f 1 0 0 -1 \"%s\" 0 0 0\n", sample_spec.path().c_str());

    // first note will fail, because ftable is not yet loaded.
    // play a silent note to trigger ftable initialization.
    score += "i 1 0 0.01 40 0\n";

    vector<CSoundUtil::PortSpec> ports = {
      CSoundUtil::PortSpec {"in", pb::PortDescription::EVENTS, pb::PortDescription::INPUT},
      CSoundUtil::PortSpec {"out:left", pb::PortDescription::AUDIO, pb::PortDescription::OUTPUT},
      CSoundUtil::PortSpec {"out:right", pb::PortDescription::AUDIO, pb::PortDescription::OUTPUT},
    };

    instrument->csound.reset(
        new CSoundUtil(
            _host_system,
            bind(&ProcessorInstrument::csound_log, this, placeholders::_1, placeholders::_2)));
    RETURN_IF_ERROR(instrument->csound->setup(orchestra, score, ports));
  } else if (spec.instrument_type_case() == pb::InstrumentSpec::kSf2) {
    const auto& sf2_spec = spec.sf2();

    instrument->fluidsynth.reset(new FluidSynthUtil(_host_system));
    RETURN_IF_ERROR(instrument->fluidsynth->setup(
                        sf2_spec.path(), sf2_spec.bank(), sf2_spec.preset()));
  } else {
    return ERROR_STATUS("Instrument type not supported");
  }

  // Make the new instrument the next one for the audio thread.
  prev_next_instrument = _next_instrument.exchange(instrument.release());
  assert(prev_next_instrument == nullptr);

  return Status::Ok();
}

void ProcessorInstrument::csound_log(LogLevel level, const char* msg) {
  _logger->log(level, "%s", msg);
}

}
