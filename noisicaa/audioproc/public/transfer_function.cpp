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

#include <math.h>

#include "noisicaa/audioproc/public/transfer_function.h"
#include "noisicaa/audioproc/public/transfer_function.pb.h"

namespace noisicaa {

float apply_transfer_function(const pb::TransferFunctionSpec& spec, float value) {
  switch (spec.type_case()) {
  case pb::TransferFunctionSpec::kFixed:
    value = spec.fixed().value();
    break;
  case pb::TransferFunctionSpec::kLinear: {
    value = (spec.linear().right_value() - spec.linear().left_value()) * (value  - spec.input_min()) / (spec.input_max() - spec.input_min()) + spec.linear().left_value();
    break;
  }
  case pb::TransferFunctionSpec::kGamma:
    value = (spec.output_max() - spec.output_min()) * powf((value  - spec.input_min()) / (spec.input_max() - spec.input_min()), spec.gamma().value()) + spec.output_min();
    break;
  default:
    break;
  }

  return value;
}

}
