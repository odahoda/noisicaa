Title: Development update (September 8)
Date: 2019-09-08

Finally [a
commit](https://github.com/odahoda/noisicaa/commit/f81b4e38895b7ab22a0a72bd6a7e76ca61a5087f) with
some major new feature: Piano roll tracks.

### What's new

#### Piano roll tracks

[[img:2019-09-08-pianoroll-track.png]]

This isn't exactly an distinguishing feature of noisicaä (as the score tracks would be), but a
pretty standard feature of a DAW, so it's good to have.

For now I just implemented the most basic editing features to make it useful. There's no editing of
CC events, no recording, no importing of MIDI files. One editing feature, which I would consider
"basic", is still missing though: copy & paste. There is some clipboard support in other track
types, but I'm not happy with it, so I didn't want to add more cruft to that. The next thing I want
to tackle is a proper design of the copy & paste system, which should be ready for current and
future use cases.

#### Some minor UI tweaks

* The position of the splitter between the track list and the graph canvas is now persisted.
* The track list stays centered when changing the time scale (`ctrl-left` and `ctrl-right` -
  hmm... that's pretty well hidden...).

### Internal changes

* Tracks are now `QWidget`s, which simplifies the UI event handling and allows to use the existing
  `PianoRoll` widget to be used for the MIDI segments.
* Extended the existing `PianoRoll` widget (as introduced for the [MIDI
  Looper](/blog/2019/06-23-development-update.md) node) to support editing and multiple MIDI
  channels.
* The existing `PianoRollProcessor` has been extended to handle multiple segments, so it can be used
  by the new `PianoRollTrack`, while keeping compatibility with existing uses by `ScoreTrack` and
  `BeatTrack`.
* The tool-based UI event handling has been streamlined.
* I switched to using `QAction`s with shortcuts, instead of explicit keyboard event handling, to
  trigger keyboard shortcuts (after I figured out how to make that work properly).
