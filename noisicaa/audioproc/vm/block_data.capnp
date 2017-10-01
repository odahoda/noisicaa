@0x82a31f158cebdce3;

using Cxx = import "/capnp/c++.capnp";
$Cxx.namespace("noisicaa::capnp");

# Absolute imports don't work reliably with Python.
using import "../../core/perf_stats.capnp".PerfStats;

struct Buffer {
  id @0 :Text;
  data @1 :Data;
}

struct BlockData {
  blockSize @0 :UInt32;
  samplePos @1 :UInt64;

  buffers @2 :List(Buffer);
  messages @3 :List(Data);
  perfData @4 :PerfStats;
}
