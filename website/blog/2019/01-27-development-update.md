Title: Development update (January 27)
Date: 2019-01-27

Just [merged the
branch](https://github.com/odahoda/noisicaa/commit/79b35d9689eccd260c854d32f1ebcc9ec2473603) for a
"command cleanup" sprint. This was mostly an internal cleanup with just a few user visible changes.

### What's new

Now some sequences of commands are merged into a single command.

Every time you make a change to the project, a command is issues for it and (in broad terms) this
command is appened to the "undo list". Turning a dial could produce dozens if not hundreds of
separate commands, and an 'undo' would undo each of those one at a time.

Now new commands might get merged into the previous command, so a sequence of many control value
changes is collapsed into a single change. And 'undo' will undo all those changes in one step.

It is also possible again to set the pitch for the note events produced by a beat track. That got
lost in some previous refactoring.

### Internal changes

The major part of the sprint was to cleanup the commands, which are internally used by the UI to
modify the opened project. Initially I used very fine grained commands, e.g. a dedicated command
`SetClef` to change the clef of a measure. The whole thing grew quite organically and I never
developed a consistend scheme.

Now I changed that to a basic [CRUD
scheme](https://en.wikipedia.org/wiki/Create,_read,_update_and_delete), i.e. most commands are
called `CreateFoo`, `UpdateFoo`, `DeleteFoo` (ok, it's really `CUD`, but whatever). And instead of
separate commands to change the various properties of an object (like the `SetClef` mentioned
above), there is now just a single `UpdateFoo` command, and which property should be changed is
determined by the presence of specific fields in that command (which are just [protocol buffer
messages](https://developers.google.com/protocol-buffers/)).

While doing those changes I also got tired of typing names like `PipelineGraphNode`. Given the
central role, which the graph and the nodes therein should now play, I renamed those to the much
more compact `Node`, `NodeConnection`, etc.

And some minor cleanups: simplify the API of the `Command` class, add factory functions for all
command protos (for some more type safety).
