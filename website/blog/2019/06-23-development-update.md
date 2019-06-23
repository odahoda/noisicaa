Title: Development update (June 23)
Date: 2019-06-23

The [latest
commit](https://github.com/odahoda/noisicaa/commit/bc9be73125c9342044d4ed0bc50c75c886f126ca) just
adds a single node type.

### What's new

#### MIDI Looper node

This node can record a few beats of MIDI events and plays them back in a time-synced loop.

For now only the most basic features are implemented. I plan to do another pass on this node at some
later time to extend the features (e.g. multiple "patches", editing MIDI events in the pianoroll
widget, etc.).

It does feature a new pianoroll widget, which is just read-only for now and displays the recorded
MIDI events. After adding editing features to this widget, I might be able to reuse it for a
pianoroll track, which I'm planning to add anyway.

And it is the first time that noisicaä can record something in
realtime. Consider this a first prototype of future recording capabilities.

### Bug fixes

* There were `.pyi` files missing for two cython modules. After adding those, `mypy` uncovered some
  minor bugs.

### Internal changes

* Initial infrastructure showing the node UIs in a dialog window. That needs some more
  work. Eventually it should be possible to pop out the UI to a window for every node.

* Some infrastructure to persist Qt properties in the project's session data.
