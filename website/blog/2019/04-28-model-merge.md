Title: The great "Model Merge" refactoring
Date: 2019-04-28

As I mentioned in the [previous post](04-25-development-update) I plan to do yet another great
refactoring. But before I jump head first into this adventure, rip everything apart and rewrite
something like 60% of the code base, I want to take a step back and describe my plan here. Looking
at the [AWStats](http://www.awstats.org/) for this website, I'm well aware that I'm just talking to
a void, but the point is really for myself to reflect on this, think it through one more time and
make sure I'm not overlooking something, which would turn this plan into a nightmare, after I
already spent a lot of time on it.

But before I start explaining my plan, I should first explain the current architecture and what the
problems and benefits of it are.

### The current architecture

The three main components of noisicaä are the UI, the project and the audio engine. The "project" is
the part, which owns the internal data structures that describe the project (the "model") and is
responsible for all changes to it (i.e. the "business logic") as well as persisting those changes to
disk. Those three components each run in different UNIX processes and communicate with a homegrown
IPC system with each other. Above those three processes is a main process, which is the one the user
creates when launching noisicaä, and it only does a little more than starting the other processes as
needed. There are also some other processes, and there is actually one project process for each
opened project, but that doesn't matter in this context.

The "model" is quite similar to e.g. the [HTML
DOM](https://en.wikipedia.org/wiki/Document_Object_Model) - a tree structure of objects, that each
have a certain set of attributes. The authoritative model lives in the project process, but the UI
has a read-only copy, which it uses to build the interface for the project. For every user action
(that modifies the model) the UI sends a command to the project process, which executes it by
performing some sequence of changes to the model. Those changes are recorded as a list of
"mutations", which are persisted on disk and sent to the UI process, where they are applied to the
read-only model, which in turn triggers the necessary interface changes. Changes to the model in the
project process can also trigger updates to the state of the audio engine, but that part of the
system is out of scope of this discussion.

That setup seems to be quite convoluted and over engineered and I cannot really disagree. But I did
have reasons, when I designed this architecture:

#### Failure domains

Software has bugs, applications will crash, but data loss or corruption in unacceptable.

Specifically the UI feels problematic, partly because I haven't really figured out how to write good
unittests for UIs, so my level of trust in my own code isn't that high.  Also the UI involves a lot
of native code, i.e. the Qt framework, so a bug often results in a segfault and not in a Python
exception, which I could handle more gracefully.

The code of the project process on the other hand is much simpler, written in pure Python and a lot
easier to test.

By putting the UI and the model in separate processes, a crash of the former cannot corrupt the latter.

#### Clean interfaces

In order to support undo/redo any change to the model must be wrapped in a command. Those commands
can then be reverted or replayed as needed. That pattern seems to be fairly common, e.g. Qt also
[offers it](https://doc.qt.io/qt-5/qundo.html), though I'm not using that implementation for
noisicaä.

Any change of the model outside of a command would lead to corruption, but only in combination of an
undo or redo, so this is hard to detect. And I know I'm lazy, so for rapid prototyping it can be
very tempting to directly change the model from the UI and then "clean it up later" - but actually
forgetting small bits here and there, which would be a source of subtle bugs. This architecture
forces me to go through that "command" interface, because the UI simply has no other way to change
the model.

### Problems of the current architecture

This architecture requires two views of the model, one in the project process and one in the UI
process, which are synchronized by sending mutations from the project process to the UI process over
IPCs. The model in the UI is limited to read-only access, whereas the model in the project process
has all the methods to implement the business logic. This results in a quite convoluted "three
dimensional" class hierarchy. I.e. every class exists three times, one abstract version, which
describes the properties of the class, one read-only implementation and one mutable
implementation. Combined with the "normal" class hierarchy (e.g. a `Track` is a subclass of `Node`,
which is a subclass of the fundamental `ObjectBase`), this results in a complex inheritance mesh,
which is pretty hard to reason about. For example there was a recent bug, which caused me a lot of
head scratching, until I noticed that I forgot one link in the inheritance mesh, but the observed
bug provided no indication that this could have been the cause.

That setup also requires a lot of boilerplate code and the code is spread across many places, which
makes it really annoying to add new classes. This point is what really caused me to questing the
current architecture and look for alternatives.

### The plan

My plan is to not create a new process to host the business logic but rather have a single model
running in the UI process (for each opened project).

But I'm paranoid about data loss or corruption, so I want to spawn a separate process per opened
project, which is responsible for writing the mutations to disk. So if the UI crashes, that writer
can flush out all pending data and the shut down gracefully.

Instead of sending a command from the UI to the project process, the command could be directly
applied to the model in the same process. This will change the order in which updates will
happen. In the old architecture, the changes will be applied completely in the project process,
before they are sent back to the UI, which applies it to its copy of the model and triggers all
required UI updates. If there is a bug in the UI, which causes it to crash while it processes the
mutation, then the command has already been completely applied and persisted in the project
process. Now the UI updates will be triggered while the command modifies the model, and if that
triggers a crash, then the command execution does not complete and nothing gets persisted. That's
probably better as it prevents the model to get into a state that would cause the UI to get into a
crash loop.

Having just a single model would remove the need for the complex class hierarchy. I could merge
those three incarnations of each class into a single class, so semantically related code moves
closer together and a lot of duplication and boilerplate should disappear. But that means that the
UI has at least technically the ability to directly change the model outside of a command execution,
sidestepping the process, which is required for a working undo system. But there is already a system
in place to monitor all changes to the model (which is used to record the mutations during the
executing of a command), so I could just use that to trigger an assertion whenever such a forbidden
model change happens.

Once that first refactoring is done, I would also want to drop the concept of explicit `Command`
classes. All I need is the sequence of mutations that happen as a result of some user action. These
mutations are what is persisted to disk and they can be applied to the project in backward (for
"undo") of forward (for "redo") direction - that's how it already works today. For that it is
sufficient to mark a section of code as "this is a command" and there's not need to actually create
some `Command` instance and pass that around.

In pseudo code the current flow looks like this:

```python
# In the UI, triggered by some widget change:
send_command('UpdateTrack', track_id=track.id, name=widget.text())

# In the project process:
class UpdateTrack(Command):
  def run(self):
    track = self.get_object_by_id(self.track_id)
    track.name = self.name
```

where `send_command()` serialized the command, sends it over IPC to the process project, which would
create the `UpdateTrack` instance, and call its `run()` method while tracking all mutations to the
model ("set the 'name' property of the object '1234' to 'New name'"), and then persisting those
mutations to disk and sending them back to the UI.

Note that `send_command()` is a coroutine, so all those steps that it triggers happen asynchronously
without blocking the UI. Which has so far not caused problems, but in theory a fast user might be
able to trigger further actions, before the results from the previous command have been applied to
the UI, which could cause all kinds of weird behavior.

With the new architecture the same would look like this:

```python
with project_mutations():
  track.name = widget.text()
```

Here the `project_mutations()` context manager would do the collection of mutations for persistence,
whereas there wouldn't be any additional action needed for "sending anything back to the UI",
because the changes are directly applied to the model that the UI already monitors.

And it should be possible that everything within that context manager is synchronous, so the user
cannot actually interact with the UI while those changes are applied (which usually should not be a
noticeable time).

### What I lose

#### Static API enforcement

In the old architecture the contract that the UI only has a read-only view of the model can be
statically checked with [mypy](http://mypy-lang.org/), because the classes that the UI sees only
have read-only properties.

This would change, because now the UI sees the one implementation of model, with all the properties
and methods, which are also needed for changing it. The UI is still not allowed to use those
(outside of the explicit execution of a command), but violations of that contract can only be caught
at runtime.

#### Graceful UI crashes

Given the old architecture, the UI process could just restart after a crash and reconnect to the
(unaffected) project process. This could even go as far as not disrupting the audio playback at all,
i.e. the audio would just continue playing, if the UI goes down, and when the UI comes back up,
everything is as if nothing happened (of course the UI might enter a crash loop, if the cause of the
crash is deterministic). Note that this is not implemented, but it could well be done with the old
architecture.

With the new architecture, the project state would be lost along the with UI, if the UI crashes, so
the project would have to be reopened as well. In theory the audio engine would still be unaffected
by such a restart, but reconnecting to it and syncing state would be much harder, if feasible at
all, so all audio engine state related to the project would have to be torn down and recreated when
the project is reopened.

So with a pessimistic outlook, where I assume that the software is unreliable and often crashing,
the old architecture would provide a better user experience. I guess I have to be more optimistic
and just make the code more reliable.

#### Remote UI

Another idea, which is also not implemented, is to allow the UI to connect over the network to a
project running on a different machine. E.g. I could imagine multiple people working on the same
piece of noise simultaneously, each one with their own workstation/laptop. That seems like it would
be fairly straight forward with the old architecture. 90% of that could be achieved by using TCP
sockets instead of UNIX domain sockets for the IPCs between the processes. But the remaining 10%
would still be tricky. Writing distributed systems is a very different pair of shoes, because you
have to be resilient against delays or network failures for every IPC. And for all kinds of file
access, you can't assume anymore that all processes see the same local filesystem.

So while this is a kind of nice idea, I'm not too sure if it's worth pursuing at all.

### What I win

#### Less code

The current architecture requires a lot of boilerplate code and the new architecture should remove a
lot of that. Less code is good.

The amount of code to implement the model should be reduced significantly, because I get rid of that
class triplication that I described above.

Also many commands are actually just changing a single property, and those could be implemented much
more efficiently. A common pattern is to have one UI widget which is connected to a property of one
object. Right now setting this connection up and synchronizing changes in both directions requires a
lot of fairly dumb code - very repetitive, but different enough to make it hard to have a generic
function taking care of it. The new architecture should help here, too.

This code reduction is really my main motivation for this refactoring, and I would be very
disappointed, if the final diff, when I merge it into master, does not have a net negative line
count.

#### Performance

The communication between the UI and the project will not go through the IPC layer, so noisicaä
might become a bit snappier. Though I don't really see a performance issue as it is today, so this
is more of a theoretical improvement.

### Verdict

I don't foresee any issues, which could be showstoppers for this refactoring, and I do think the
gains are worth the losses.

I do have to admit that this write up didn't grant me any new insights. I already had a bunch of
unordered notes and my hope was that turning those into this more structured document would cause me
to see things, which I have missed before. But I'm either still missing something important or there
wasn't anything missing in the first place.
