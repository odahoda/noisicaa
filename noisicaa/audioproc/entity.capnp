@0xe06aeab75c370f0b;

struct Entity {
  id @0 :Text;

  enum Type {
    audio @0;
    atom @1;
  }
  type @1 :Type;

  size @2 :UInt32;
  data @3 :Data;
}
