// -*- mode: c++ -*-

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

#ifndef _NOISICAA_AUDIOPROC_VM_PROCESSOR_SPEC_H
#define _NOISICAA_AUDIOPROC_VM_PROCESSOR_SPEC_H

#include <map>
#include <memory>
#include <string>
#include <vector>
#include <stdint.h>
#include "noisicaa/core/status.h"

namespace noisicaa {

using namespace std;

enum PortType {
  audio,
  aRateControl,
  kRateControl,
  atomData,
};

enum PortDirection {
  Input,
  Output,
};

class PortSpec {
public:
  PortSpec(const string& name, PortType type, PortDirection direction);

  string name() const { return _name; }
  PortType type() const { return _type; }
  PortDirection direction() const { return _direction; }

private:
  string _name;
  PortType _type;
  PortDirection _direction;
};

class ParameterSpec {
public:
  enum ParameterType {
    String,
    Int,
    Float,
  };

  ParameterSpec(ParameterType type, const string& name);
  virtual ~ParameterSpec();

  ParameterType type() const { return _type; }
  string name() const { return _name; }

private:
  ParameterType _type;
  string _name;
};

class StringParameterSpec : public ParameterSpec {
public:
  StringParameterSpec(const string& name, const string& default_value);

  string default_value() const { return _default_value; }

private:
  string _default_value;
};

class IntParameterSpec : public ParameterSpec {
public:
  IntParameterSpec(const string& name, int64_t default_value);

  int64_t default_value() const { return _default_value; }

private:
  int64_t _default_value;
};

class FloatParameterSpec : public ParameterSpec {
public:
  FloatParameterSpec(const string& name, float default_value);

  float default_value() const { return _default_value; }

private:
  float _default_value;
};

class ProcessorSpec {
public:
  ProcessorSpec();

  Status add_port(const string& name, PortType type, PortDirection direction);
  uint32_t num_ports() const { return _ports.size(); }
  PortSpec get_port(int idx) const { return _ports[idx]; }

  Status add_parameter(ParameterSpec* param);
  StatusOr<ParameterSpec*> get_parameter(const string& name) const;

private:
  vector<PortSpec> _ports;
  map<string, unique_ptr<ParameterSpec>> _parameters;
};

}  // namespace noisicaa

#endif
