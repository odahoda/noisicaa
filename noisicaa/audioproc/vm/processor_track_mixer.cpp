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

#include "noisicaa/audioproc/vm/misc.h"
#include "noisicaa/audioproc/vm/processor_track_mixer.h"

namespace noisicaa {

ProcessorTrackMixer::ProcessorTrackMixer(const string& node_id, HostData *host_data)
  : ProcessorCSoundBase(node_id, "noisicaa.audioproc.vm.processor.track_mixer", host_data) {}

Status ProcessorTrackMixer::setup(const ProcessorSpec* spec) {
  Status status = ProcessorCSoundBase::setup(spec);
  RETURN_IF_ERROR(status);

  string orchestra = R"---(
0dbfs = 1.0
ksmps = 32
nchnls = 2

ga_in_l chnexport "in:left", 1
ga_in_r chnexport "in:right", 1
ga_out_l chnexport "out:left", 2
ga_out_r chnexport "out:right", 2
gk_gain chnexport "gain", 1
gk_muted chnexport "muted", 1
gk_pan chnexport "pan", 1

instr 2
  if (gk_muted > 0.5) then
    ga_out_l = 0.0
    ga_out_r = 0.0
    kgoto end
  endif

  ; pan signal
  i_sqrt2   = 1.414213562373095
  k_theta   = 3.141592653589793 * 45 * (1 - gk_pan) / 180
  a_sig_l = i_sqrt2 * cos(k_theta) * ga_in_l
  a_sig_r = i_sqrt2 * sin(k_theta) * ga_in_r

  ; apply gain
  k_volume = db(gk_gain)
  ga_out_l = k_volume * a_sig_l
  ga_out_r = k_volume * a_sig_r

end:
endin
)---";

  string score = "i2 0 -1\n";

  status = set_code(orchestra, score);
  RETURN_IF_ERROR(status);

  return Status::Ok();
}

void ProcessorTrackMixer::cleanup() {
  ProcessorCSoundBase::cleanup();
}

}
