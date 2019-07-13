Title: Development update (July 14)
Date: 2019-07-14

This [commit](https://github.com/odahoda/noisicaa/commit/66011fa94a8e5eca2a5ce38f3d47a211a8f7ac66)
implements most of what I was talking about [last week](/blog/2019/07-06-development-update).

### What's new

#### Variable type ports

Ports can now be declared with multiple types. Two ports can be connected, if they have at least one
type in common.

This feature is currently used for

* the Oscilloscope node, so it can also graph audio and k-rate control signals.
* the Oscillator node, so its input and output ports can be connected to any audio or a-rate control
  signal.

More nodes should make use of that feature in the future. Ideally this should remove the pain of
constantly thinking about k-rate vs. a-rate control signals, but this feature is limited to builtin
nodes. So I might still need some way of automatically converting between incompatible port types. I
still don't like the idea of an implicit conversion of a-rate control signals to k-rate, because
that's a lossy conversion. But I also expect that to be frequently needed, because plugins generally
use k-rate control values for their controls.

### Internal changes

* Processors now get references to `Buffer` instances, instead of raw data pointers. The processor
  can query the type of the buffer to determine which of the declared types is actually being used.

* Tracking the connected buffers is now done completely in the `Processor` base class. Subclasses
  just had a lot of trivial code to reimplement the same thing over and over again, but there was no
  real need for that level of customization.

* Refactored tests for processors, removing a lot of redundant code. Because of this, this commit
  even has a slightly negative line count!

* Connections now track their type. This change is compatibility breaking.
