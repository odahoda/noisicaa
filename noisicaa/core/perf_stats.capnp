@0xf5d957e90b340908;

struct Span {
  id @0 :UInt64;
  name @1 :Text;
  parentId @2 :UInt64;
  startTimeNSec @3 :UInt64;
  endTimeNSec @4 :UInt64;
}

struct PerfStats {
  spans @0 :List(Span);
}
