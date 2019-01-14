Title: Development update (January 14)
Date: 2019-01-14

I just finished a "MIDI in" sprint and [merged it into the master
branch](https://github.com/odahoda/noisicaa/commit/f4ce7f53d2f031967d07d48fbaf279e3aac5332b).

Oops, I just noticed that I forgot to remove the commit messages from the branch. I usually to a
`git merge --squash [branch]`, so there's just one big commit to the master branch, instead of
dozens of small ones, and also write a commit message summarizing all the changes. git helpfully
prepopulates the commit message with all the individual commit messages from the branch, which I
then just remove. Except for today...

### What's new

There is now a "MIDI source" node, which can be used to feed MIDI events from any ALSA device, e.g. you USB keyboard, into the graph.

[[img:2019-01-14-development-update.png]]

There used to be some similar functionality written in Python, but that lived on the UI side and
MIDI events were fed to the backend via RPCs. And that implementation gradually fell apart, as I was
refactoring things over the past month. So the only place where it was used (the onscreen keyboard
in the instrument library, which could be connected to a real MIDI keyboard) didn't even work
anymore.

The new implementation is pure C++ and MIDI events are collected directly in the audio
thread. Of course except for that onscreen keyboard, which still has to send it's MIDI events via
RPC to the engine. But that's now done using the same mechanism for communicating with node
processors, which is also used for other things.
