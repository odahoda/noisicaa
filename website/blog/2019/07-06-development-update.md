Title: Development update (July 6)
Date: 2019-07-06

Today's [commit](https://github.com/odahoda/noisicaa/commit/a00e72ed49650be1859b1ac910f150976d214713) has a number of new node types. And pictures!

### What's new

#### Metronome

[[thumb:2019-07-06-metronome.png]] The simplest imaginable metronome. It just makes a tick on every
beat (if playback is running). But you can select the sample that it should play. The audio is not
sent directly to your speakers, you have to wire it up just like any other node.

#### MIDI Monitor

[[thumb:2019-07-06-midi-monitor.png]] The MIDI Monitor just displays a list of the MIDI events that
it receives on its input port. Inspired by [KMidimon](http://kmidimon.sourceforge.net/), but much
simpler. I mostly wanted it for debugging of other MIDI nodes.

#### MIDI Velocity Mapper

[[thumb:2019-07-06-midi-velocity-mapper.png]] The MIDI Velocity Mapper takes a stream of MIDI
events, tweaks the velocity of `noteon` events (other MIDI events are left untouched) and then just
passes them through to its output port.

The main motivation is the little [AKAI APC Key 25](https://www.akaipro.com/apc-key-25) MIDI
controller, which I have on my desk and sometimes use to feed MIDI data into noisicaä (or any other
audio software). It's nice, because it's small and always in arms reach, if I want to doodle
around. But the keys are IMHO not very good. They feel pretty cheap and I have to hit them very
hard to get even a medium velocity out of it. Perhaps that's ok for professional musicians, or
when you're on stage and pumped up with adrenaline. But for a bloody amateur like me, who has
trouble even hitting the right keys, that makes it very hard to use. Putting more energy into my
fingers just reduces the precision and I keep hitting multiple keys at the same time. The Velocity
Mapper basically allows me to adjust the sensitivity of the keyboard.

#### Control Value Mapper

[[thumb:2019-07-06-cv-mapper.png]] The transfer function, which I implemented for the MIDI Velocity
Mapper, was implemented in a way, which is easy to reuse elsewhere. So I just added another node,
which applies such a function to an a-rate control value.

The function just maps some input value to an output value. It currently supports three different
functions:

"Fixed value:" As the name suggests, the output is always a fixed value. Not very useful for control
values, but it makes more sense for the MIDI Velocity Mapper, where you might want to just ignore
the incoming velocities.

"Linear:" Useful for mapping e.g. a [-1,1] signal to [0,1].

"Gamma:" This uses the same function as the "Gamma Correction" known in image processing (or your
monitor settings). Basically brightens or darkens a signal, while still maintaining the full value
range.

#### Oscilloscope

[[thumb:2019-07-06-oscilloscope.png]] This should mostly work like a real oscilloscope. I
think. Because I never used one.

I felt the need to add this one, because while testing out the Control Value Mapper something "did
not sound right". But without being able to visualize the signals, I couldn't tell what the problem
was. It turned out that Csound's [lfo](http://www.csounds.com/manual/html/lfo.html) opcode does not
work as I expected. The manual makes it look like it can produce both k- and a-rate signals. But it
turns out that even when using it with a-rate output, the actual value is only computed at
k-rate. So what I heard was basically an LFO with a super low sample rate.

Currently you can only feed a-rate control values into it.

### Internal changes

* Created a base class for testing processors, removing a bunch of code, which I duplicated over and
  over.

### What's next?

While working on those new nodes, it became quite annoying that ports have different types that you
can't easily connect. E.g. plugins generally use k-rate control values for their controls, whereas
my builtin nodes prefer a-rate control values. So if I have an LFO producing an a-rate output, I
can't use it directly to feed some control of a plugin. Or the Oscilloscope should also be able to
display audio data. And so on.

In some cases it can make sense to allow connections between ports with different types. A k-rate
control output could just be interpolated to feed into an a-rate control input. An audio output can
feed directly into an a-rate control port (not the other way around, because control values can be
in any range, and you really don't want to feed that into your amp). So noisicaä could do some
auto-conversion has needed.

Or nodes could be able to accept different connections to their ports. E.g. the Oscilloscope would
declare that its input port can accept k-rate and a-rate control values as well as audio
signals. And then just process that input appropriately. But that capability would be limited to
builtin nodes, because plugin don't know how to do that.

So that's probably what I'm going to work on next.
