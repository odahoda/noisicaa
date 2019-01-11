Title: Introducing noisicaä - A simple music editor
Date: 2015-11-29

I don't know much about music, but it's a topic that interests me.

I don't play any instruments and I'm too old or too lazy to learn one. Probably both.

But I'm one of those computer persons, so I would naturally use a computer to make music - or at
least attempt to.

So I looked around what software is out there, but the stuff I found didn't get me terribly
excited. Now I have to add that I'm using Linux (Kubuntu on my desktop to be more specific) and
while I also have Windows on my machine, I wouldn't want to use it - except as a bootloader for
Steam. I also didn't look at commercial software, just what's out there in the open source
world. That limits the selection. And the stuff that actually exists in that small subsection of the
market is either too simple or overwhelmed me a ton of options and possibilities that I don't know
how to use, because I don't actually know what that stuff means.

On the other hand I still remember playing around with the [Deluxe Music Construction
Set](https://en.wikipedia.org/wiki/Deluxe_Music_Construction_Set) on my Amiga back in the days. And
that level of complexity (or the lack thereof) feels like exactly the thing that would be
appropriate for me today.

So because I couldn't find any existing software that I liked, I started writing my own. Also
writing code is fun, so I don't really need a reason.

I'm also using this opportunity to play with some fancy tools, which I haven't used yet: Python3
(it's about time), Cython (sounded like a cool toy, but I never had a reason to use it before) and
Qt5 (I've been using wx for UIs in the past, but I like Qt way more now).

I'm also giving git another try. Well, we'll see. That has been quite a lackluster experience in the
past.

### What's different about noisicaä?

noisicaä uses classical musical notation. Putting notes onto staves, clefs, measures. etc. Most
"modern" software seems to focus on a sequencer style interface. My little bit of knowledge about
music is stuck in the time when I had music in school, and continuing from that point seems to be
easiest for me. Perhaps later I'll figure out that the piano roll UI of sequencers is indeed more
powerful than the system that been used by Bach and Mozart back in the days. But the software can
make that transition together with me, as I acquire more skills.

Another thing that seems popular, especially in the realm of commercial software (which I can only
tell from seeing random screenshots on random websites, since I never used any of these), is that
the UI simulates existing hardware. That might be nice for people with existing experience in making
music using real instruments and studio hardware. But for me that's just another obstacle, because
in addition to learning about the musical domain itself, I would also have to deal with a user
interface that doesn't follow known guidelines. At least known to someone who never set foot in a
music studio, but worked with computer for the past 25 years.

So noisicaä's UI rather follows established schemes that you would also find in IDE, office suites,
and the likes.

### Features

Not a lot yet. This is still pre-alpha state software.

There's some basic editing and you can play it back. The instruments are currently rendered using
[FluidSynth](http://www.fluidsynth.org/), i.e. it uses soundfonts. I have vague plans to
also support plain .wav files as samples, or use synthesizers to create
instruments. [Csound](https://csound.com/) seems like the kind of arcane but powerful system
that I could like a lot.

Of course the music should eventually be rendered as .flac, .ogg, etc. files, but that doesn't exist
yet.

There should be some support for filters and general mixing/production features, so I get a little
bit more than the typical MIDI
sounds. [LADSPA](https://en.wikipedia.org/wiki/LADSPA)/[LV2](http://lv2plug.in/) plugins and again
Csound seem to be the right tools for that.

I'll also do something with MIDI input. There's a little MIDI controller here on my desk, that wants
to be entertained. But probably not real-time recording, because I could play anything in real-time
that's worth recording.

And in the further future I'm also thinking about some hybrid system which mixes composed tracks
with recorded tracks - where the source of the recording will probably be my wife playing the guitar
or bass.

And who knows what. That'll depend a lot on where my learning curve takes me. I will use this
project to implement those things that I learn about music, so I can apply them.

### What, music software in Python?

That's right. People seem to make a big fuzz about latency, real-time support in the kernel and that
kind of stuff. They probably know better than I, but I'll ignore that advice anyway. Most of the
coding is around the UI, persistence, etc. and not involved in the playback at all. And despite not
having spent a lot of time into optimizing anything, I haven't observed any buffer underruns during
playback yet. Perhaps using a totally overpowered desktop is just good enough (though it's already a
few years since that machine was "high end").

Also I don't see noisicaä as a tool to be used on stage for live performances. So occasional
glitches do not worry me a lot.

And then there's [Cython](http://cython.org/), which I started using mostly for interacting with C
libraries. I already use it for some of the bit crunching parts - not because those already needed
optimization, but just because I wanted to play with it a bit more (aka. premature optimization).

### So... you want to make music?

That's the weak spot of this whole enterprise. I seriously doubt that I have the creativity and
artistic skills to produce something that could actually be called music. Or warrant all the effort
I'm now putting into this. Even after I learned all the theory that there is to learn and created
the greatest software that any artist could dream of.

Bah, who cares...
