#ifndef _NOISICORE_PROCESSOR_SPEC_H
#define _NOISICORE_PROCESSOR_SPEC_H

#include <map>
#include <memory>
#include <string>
#include <vector>
#include <stdint.h>
#include "status.h"

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

enum ParameterType {
  String,
};

class ParameterSpec {
 public:
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

class ProcessorSpec {
 public:
  ProcessorSpec();

  Status add_port(const string& name, PortType type, PortDirection direction);
  uint32_t num_ports() const { return _ports.size(); }
  PortSpec get_port(int idx) const { return _ports[idx]; }

  Status add_parameter(ParameterSpec* param);
  Status get_parameter(const string& name, ParameterSpec** param) const;

 private:
  vector<PortSpec> _ports;
  map<string, unique_ptr<ParameterSpec>> _parameters;
};

}  // namespace noisicaa

#endif
