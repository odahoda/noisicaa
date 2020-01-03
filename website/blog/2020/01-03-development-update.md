Title: Development update (January 3)
Date: 2020-01-03

There hasn't been an update in a while. And there hasn't been a lot of work on noisicaä either.

I started a new sprint back in September, but then there was a vacation, and that yanked me out of my
routine, and it took me an awful long time to find my way back.

It wasn't like I was not doing anything. I spent some time improving my emacs configuration,
including setting up a configuration for my daughter's novel writing ambitions. We bought one of
those all-in-one printer-scanner-fax[^1] things, which triggered me to write the beginnings of a
little document management system, so we can eventually move to a (mostly) digital archival for
documents that you're supposed to keep. I reinstalled my dying home server on a Raspberry Pi 4,
which went surprisingly smooth.

But those were the kind of in-between projects that you do to distract yourself, not something to
focus. But perhaps that is just what I need every once in a while, as I feel that I have rebuilt
quite a bit of energy over the past few days. Now I "just" have to direct that energy towards
noisicaä.

Anyway. Just to wrap up the stuff that I was doing (mostly back in September), here's the latest
[commit](https://github.com/odahoda/noisicaa/commit/bae6940b3649995e59ce4c0a0670a321f49b5682).
There are still plenty of bullet points on my checklist, which I initially planned to do in that
sprint, but I'll defer those to another time.

Even the commit was already done three weeks ago, and I couldn't get myself to write the
accompanying blog post until now.

### What's new

#### Track list improvements

[[thumb:2020-01-03-track-list.png]] I did quite a bit of refactoring and improving of the track
list. Tracks can now be resized vertically and reordered with drag-n-drop. There's also a new zoom
function which zooms in both dimensions, but that's only accessible via keyboard shortcuts with no
visible hint that those exist. And so far only pianoroll tracks currently handle resizing correctly.

#### Load test projects

[[thumb:2020-01-03-loadtest-project.png]] There's a hidden feature (I'm not telling you how to
access it &#8212;&nbsp;read the source to find out) to create a new project filled with random
data. This is really just a development tool for myself, so the usability is not that great and that
won't change. Like the name suggests, I can use this feature to stress test noisicaä and find
performance bottlenecks.

### Internal changes

- Some refactoring of the process startup, which previously triggered some scary warning messages
  (`"RuntimeWarning: 'noisicaa.core.process_manager' found in sys.modules after import of package
  'noisicaa.core', but prior to execution of 'noisicaa.core.process_manager'; this may result in
  unpredictable behaviour"`).

- A new `move` mutation type to efficiently reorder lists.

[^1]: Yeah, that stuff is still around. I have no use it or intend to even plug it into a telephone
    socket. But it's not like we wasted money on a feature that we're not using, given how dirt
    cheap the hardware itself is &#8212;&nbsp;until you have to buy the first toner refill.
