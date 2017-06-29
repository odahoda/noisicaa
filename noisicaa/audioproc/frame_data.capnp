@0xbb9febffba89653f;

using import "entity.capnp".Entity;
using import "../core/message.capnp".Message;

struct FrameData {
  frameSize @0 :UInt32;
  samplePos @1 :UInt64;

  entities @2 :List(Entity);
  messages @3 :List(Message);
}
