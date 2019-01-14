Title: Development update (January 10)
Date: 2019-01-10

Development made had a small hiatus in second half of 2018, but in
December - thanks to a lot of spare time - I picked coding up again.

The biggest and most visible change was that I completely rethought
the general idea behind noisicaä. In the beginning I started out with
something that should resemble a piece of paper with staves on it,
that lets you easily create, edit and play music, and I only
envisioned basic audio processing features. Over time that turned into
something much more like the typical DAW with tracks and plugins and
all that stuff. But I wasn't very happy about the way DAWs typically
manage the audio processing. In my mind manipulating the actual
processing graph feels like the most intuitive way, something like
[Pure Data](https://puredata.info/) or a modular synth. Which also
happens to be the way the engine works internally. I didn't quite know
how to make this properly accessible, so I just had something basic in
place.

At some point I came across a [video
demo](https://www.youtube.com/watch?v=pMXhnBANiMA) for
[BespokeSynth](https://github.com/awwbees/BespokeSynth) and I really
liked the general approach of that UI. Eventually I started thinking
more about what noisicaä should actually be. The primary use case has
always been musical composition, and that doesn't change. But most
apps have some kind of metaphor to the real world that they're built
upon (e.g. sheet music for [MuseScore](https://musescore.org/),
recording studio for [Ardour](https://ardour.org/), etc.). And I
simply decided that noisicaä's foundational idea should be the modular
synth.

So made did a major refactoring, putting the processing graph onto the
center stage, both in terms of internal code structure, as well as on
the UI. There are still tracks, and they are prominently featured on
the UI, because time and temporal editing remains to be a central
ingredient. But e.g. now you add a 'Score Track' node to the
processing graph, which will also add an editable track, instead of
the other way around.

Another major change during the past weeks was that I finally got
around to purge all Python from the critical path in the audio
thread. This is now all C++ and hopefully realtime safe. Now playback
even at smaller block sizes is much more reliable.

Finally on the more organizational side, I adopted a scheme of doing
"sprints". Well... I know that there is some development methodology,
which uses the term "sprint", but I don't even know which one that is,
what it exactly means by that word, nor do I intend to adopt any
methodology or become serious about project management or anything
evil like that. But it seems to work quite well to structure that
gigantic pile of ideas, which I want to implement, into reasonably
sized chunks, and then spend a week or two tick off all the boxes for
one of those chunks. And I just call those chunks "sprints".

And maybe, just maybe... if every other week or so, when I merged
all the changes for a completed sprint into the master branch, and
have that nice feeling of accomplishment... maybe that also makes me
want to write a post with a short update of what I did. Otherwise this
blogging thing simply doesn't seem to work for me, as you can tell
from the frequency of postings.

