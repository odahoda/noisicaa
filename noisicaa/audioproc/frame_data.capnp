@0xbb9febffba89653f;

using import "entity.capnp".Entity;
using import "pipeline_mutations.capnp".PipelineMutation;
using import "../core/message.capnp".Message;
using import "../core/perf_stats.capnp".PerfStats;

struct FrameData {
  frameSize @0 :UInt32;
  samplePos @1 :UInt64;

  entities @2 :List(Entity);
  messages @3 :List(Message);
  pipelineMutations @4 :List(PipelineMutation);
  perfData @5 :PerfStats;
}
