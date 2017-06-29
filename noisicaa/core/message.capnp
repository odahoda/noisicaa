@0xb5afa1e45874d1ef;

enum Key {
  sheetId @0;
  trackId @1;
}

struct Label {
  key @0 :Key;
  value @1 :Text;
}

struct Labelset {
  labels @0 :List(Label);
}

enum Type {
  atom @0;
}

struct Message {
  labelset @0 :Labelset;
  type @1 :Type;
  data @2 :Data;
}
