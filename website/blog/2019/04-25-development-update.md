Title: Development update (April 25)
Date: 2019-04-25

The latest
[commit](https://github.com/odahoda/noisicaa/commit/5ca602b9e41e0cbfaa38f528a6a756e3aab7d803)
primarily adds a handful of new builtin nodes.

This "MIDI CC to CV" node actually poses an interesting problem. It is inherent to MIDI controllers
that only changes of the controller positions are communicated, which implies that on startup you
don't know what the current position of the controller is until the first change event comes in.

You could use the control values coming from the MIDI CC to CV node to control some sounds and tweak
the controllers to get the sound that you want, but when you then close the project and open it
again on the next day, the control values are reset back to zero. If you're lucky, then the MIDI
controller is still plugged in and the knobs are still in yesterdays position, so you could wiggle
every knob just a little bit to get the system back to almost the same state as it was.

noisicaä should arguably store the most recent value of each controller, but how should that exactly
work? If every value change is applied as a project mutation, then that implies that these can be
undone, which is kinda weird (how should the software undo a physical movement of some piece of
hardware?), but ok. But this node doesn't have to be connected to some actual hardware input. It
could just as well get its input from some node that generates CC events, e.g. a recorded MIDI
stream or some generative music thing. Then playing back the project would modify the project and
that really doesn't make sense.

My best answer to this problem is that this node simply should not be used to connect hardware
controllers to a project. It should only be used to converted recorded or generated MIDI CCs into
control values, and the current behavior will stay, i.e. the current values is transient and not
persisted. And at some future time it should be possible to link control dials to a hardware
controller - not via a port connection, but rather as an additional UI option. Those value changes
would then be recorded as project mutations, so they become persistent, i.e. the hardware controller
would just be used instead of the mouse, but the effect would be the same.

Another thing that became apparent during this sprint is that the amount of boilerplate code to add
new nodes is still way to big. While I could have easily gone on and add more nodes - especially
ones that can be fully implemented in Faust are pretty easy to do now, i.e. pure DSPs, which don't
interact with MIDI events or need more than the most basic UI. But the urge to do yet another huge
refactoring kept growing. So now I'm at a point where I say to myself: "Look, I added some new
features, can I now [do something fun again](03-03-development-update)?" And I can't really say "no"
to myself.

### What's new

The following new node types have been added:

* Oscillator: a simple oscillator with sine, sawtooth and square waveforms.
* Noise: white/pink noise generator.
* VCA, with optional smoothing of the control signal.
* Step Sequencer, with up to 128 steps and 100 channels, where each channel can produce either a
  control value, a gate signal or a short trigger signal.
* MIDI CC to CV, converting MIDI controller change events into a control signal.

The insert node dialog gained some icons and displays information about the nodes, to give you some
more hints about what you're inserting beyond the name itself.

### Internal changes

* A new ProcessorFaust class for nodes based on [faust](https://faust.grame.fr/index.html). For now
  only supports statically compiled code, i.e. users cannot (yet) edit and run arbitrary faust code,
  like it is possible with Csound.
* Ports can be specified with a list of "label -> value" mappings, and the UI turns that into a
  combobox instead of a dial.
