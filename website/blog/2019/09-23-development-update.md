Title: Development update (September 23)
Date: 2019-09-23

As [mentioned before](/blog/2019/09-08-development-update) I worked on the copy&paste system, which
has just been
[committed](https://github.com/odahoda/noisicaa/commit/f4c583ee5b9da3f85cfabe6eaaa91bfaa8ff79cb).

### What's new

The only user visible change is that you can now copy&paste segments in piano roll tracks, as well
as MIDI notes within segments.

### Internal changes

noisicaä now uses the system clipboard (via `Qt5`'s API) to store the copied items. The items are
serialized in a common protobuf message, with extensions for the various things that can be
copied. That new system has been used to add copy&paste support to piano roll tracks and the
existing copy&paste functionality for score and beat tracks has been migrated to it.

There is now a single class, which keeps track of the clipboard contents and the current focus
widget. It also owns the `QAction`s for "Cut", "Copy", "Paste" and "Paste as link", and decides
which of these actions are enabled based on the current state. If one of those actions gets
triggered, it is sent to the current focus widget, which then implements the actual business logic.
That seems to work pretty well, and the code looks much cleaner than the previous dispatching of
method calls. But I'm not 100% sure that I covered all cases in which the state of the actions needs
to be updated. I have the feeling that there are conditions in which e.g. "Copy" should be enabled,
but isn't, or vice-versa.

Another thing where I'm not quite finished is how the sets of selected items are managed. Currently
the three widgets, which do support selections, implement that independently.  So there's a bit of
repetitive code, which is quite similar, but with more or less subtle differences. Some of those
differences should be removed, so all widgets exhibit the same behavior (which is currently quite
inconsistent, including very different colors to highlight selected items). But other differences
are inherent to the nature of those widgets. E.g. items, which are lined up on a linear time line
(like segments on a piano roll track) are different from items places on a two dimensional canvas
(like notes in a piano roll segment or nodes on the pipeline graph canvas).  I'd like to get a
better feeling for what should be shared and what is specific to each widget, before I try to come
up with some class that factors out the selection management.
