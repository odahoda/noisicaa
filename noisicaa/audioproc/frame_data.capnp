@0xbb9febffba89653f;

using import "entity.capnp".Entity;

struct FrameData {
  frameSize @0 :UInt32;
  samplePos @1 :UInt64;

  entities @2 :List(Entity);
}
