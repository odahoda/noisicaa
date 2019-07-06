// -*- mode: c++ -*-

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

#ifndef _NOISICAA_AUDIOPROC_PUBLIC_TRANSFER_FUNCTION_H
#define _NOISICAA_AUDIOPROC_PUBLIC_TRANSFER_FUNCTION_H

#include <string>

namespace noisicaa {

namespace pb {
  class TransferFunctionSpec;
}

float apply_transfer_function(const pb::TransferFunctionSpec& spec, float value);
float apply_transfer_function(const std::string& serialized_spec, float value);

}  // namespace noisicaa

#endif
