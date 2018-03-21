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

#include "noisicaa/audioproc/engine/control_value.h"

namespace noisicaa {

ControlValue::ControlValue(ControlValueType type, const string& name)
  : _type(type),
    _name(name) {}

ControlValue::~ControlValue() {}

FloatControlValue::FloatControlValue(const string& name, float value)
  : ControlValue(ControlValueType::FloatCV, name),
    _value(value) {}

IntControlValue::IntControlValue(const string& name, int64_t value)
  : ControlValue(ControlValueType::IntCV, name),
    _value(value) {}

}  // namespace noisicaa
