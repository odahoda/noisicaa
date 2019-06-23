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

#include "noisicaa/node_db/node_description.pb.h"
#include "noisicaa/builtin_nodes/control_track/processor.h"
#include "noisicaa/builtin_nodes/sample_track/processor.h"
#include "noisicaa/builtin_nodes/instrument/processor.h"
#include "noisicaa/builtin_nodes/pianoroll/processor.h"
#include "noisicaa/builtin_nodes/mixer/processor.h"
#include "noisicaa/builtin_nodes/custom_csound/processor.h"
#include "noisicaa/builtin_nodes/midi_source/processor.h"
#include "noisicaa/builtin_nodes/oscillator/processor.h"
#include "noisicaa/builtin_nodes/vca/processor.h"
#include "noisicaa/builtin_nodes/noise/processor.h"
#include "noisicaa/builtin_nodes/step_sequencer/processor.h"
#include "noisicaa/builtin_nodes/midi_cc_to_cv/processor.h"
#include "noisicaa/builtin_nodes/midi_looper/processor.h"
#include "noisicaa/builtin_nodes/midi_monitor/processor.h"

namespace noisicaa {

StatusOr<Processor*> create_processor(
    const string& realm_name, const string& node_id, HostSystem* host_system,
    const pb::NodeDescription& desc) {
  assert(desc.has_processor());

  if (desc.processor().type() == "builtin://cv-generator") {
    assert(desc.type() == pb::NodeDescription::PROCESSOR);
    return new ProcessorCVGenerator(realm_name, node_id, host_system, desc);
  } else if (desc.processor().type() == "builtin://instrument") {
    assert(desc.type() == pb::NodeDescription::PROCESSOR);
    return new ProcessorInstrument(realm_name, node_id, host_system, desc);
  } else if (desc.processor().type() == "builtin://sample-script") {
    assert(desc.type() == pb::NodeDescription::PROCESSOR);
    return new ProcessorSampleScript(realm_name, node_id, host_system, desc);
  } else if (desc.processor().type() == "builtin://pianoroll") {
    assert(desc.type() == pb::NodeDescription::PROCESSOR);
    return new ProcessorPianoRoll(realm_name, node_id, host_system, desc);
  } else if (desc.processor().type() == "builtin://mixer") {
    assert(desc.type() == pb::NodeDescription::PROCESSOR);
    return new ProcessorMixer(realm_name, node_id, host_system, desc);
  } else if (desc.processor().type() == "builtin://custom-csound") {
    assert(desc.type() == pb::NodeDescription::PROCESSOR);
    return new ProcessorCustomCSound(realm_name, node_id, host_system, desc);
  } else if (desc.processor().type() == "builtin://midi-source") {
    assert(desc.type() == pb::NodeDescription::PROCESSOR);
    return new ProcessorMidiSource(realm_name, node_id, host_system, desc);
  } else if (desc.processor().type() == "builtin://oscillator") {
    assert(desc.type() == pb::NodeDescription::PROCESSOR);
    return new ProcessorOscillator(realm_name, node_id, host_system, desc);
  } else if (desc.processor().type() == "builtin://vca") {
    assert(desc.type() == pb::NodeDescription::PROCESSOR);
    return new ProcessorVCA(realm_name, node_id, host_system, desc);
  } else if (desc.processor().type() == "builtin://noise") {
    assert(desc.type() == pb::NodeDescription::PROCESSOR);
    return new ProcessorNoise(realm_name, node_id, host_system, desc);
  } else if (desc.processor().type() == "builtin://step-sequencer") {
    assert(desc.type() == pb::NodeDescription::PROCESSOR);
    return new ProcessorStepSequencer(realm_name, node_id, host_system, desc);
  } else if (desc.processor().type() == "builtin://midi-cc-to-cv") {
    assert(desc.type() == pb::NodeDescription::PROCESSOR);
    return new ProcessorMidiCCtoCV(realm_name, node_id, host_system, desc);
  } else if (desc.processor().type() == "builtin://midi-looper") {
    assert(desc.type() == pb::NodeDescription::PROCESSOR);
    return new ProcessorMidiLooper(realm_name, node_id, host_system, desc);
  } else if (desc.processor().type() == "builtin://midi-monitor") {
    assert(desc.type() == pb::NodeDescription::PROCESSOR);
    return new ProcessorMidiMonitor(realm_name, node_id, host_system, desc);
  }

  return ERROR_STATUS("Invalid processor type %d", desc.processor().type());
}

}  // namespace noisicaa
