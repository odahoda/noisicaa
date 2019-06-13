Title: Development update (June 13)
Date: 2019-06-13

Time for the [next
commit](https://github.com/odahoda/noisicaa/commit/8d7c0cc0d44d270e8ba08a6937d2e921f4c6d758). This
was mostly about streamlining the setup process for the application, but I also added some more new
stuff, which felt related. I could have added a lot more features around managing projects, but I
postponed those to another time.

### What's new

#### More responsive startup

When starting the application, the window now opens much earlier, showing a process bar while the
application is initializing. I decided against using the typical "splash window", because by
directly opening the main application window, I can already show the "open project" dialog and let
the user choose which project to open, before the application is fully initialized. This probably
cuts a few seconds from starting the application to the project being opened. Thanks to Python's
[asyncio](https://docs.python.org/3/library/asyncio.html) package, which I've been using anyway,
this didn't require any significant changes, nor did I have to bother with background threads and
how to communicate with the UI, etc. Coroutines FTW!

#### New "open project" dialog

This "open project" dialog is now a custom widget in the main window (on any new project tab), and
not the standard file dialog. In terms of features and usability it probably needs some more
polishing, but it should be good enough for now.

#### Project debugger

And then there's an initial version of a "project debugger". It can only display the list of
mutations, and you can "truncate" the list, i.e. remove the latest mutations. This can be useful, if
some action got the project into some broken state, so it fails to open. Then you can try to repair
the project by removing the offending changes. Hopefully this won't be needed that often by future
end-users, but right now during development, this happens quite frequently. So far I have just
discarded whatever project I had opened, but at some point I should really start and try to make
something proper with noisicaä. Something I wouldn't just toss away because of some silly bug...

#### "New project" dialog

There's a silly gimmick in the dialog for entering the name of a new project. The project name is
pre-filled by a "random song title generator". It comes up with some funny names and who knows,
perhaps inspires some awesome noises. The rules for those names come from the [Time of Forbidden
Spells](https://github.com/Sundin/Tome-of-Forbidden-Spells), which just happened to be the most
promising candidate when I searched for ["song title generator" on
GitHub](https://github.com/search?q=song+title+generator&type=Repositories). The titles are a
Metal-style, which might not be everyone's cup of tea, nor the most appropriate for noisicaä, which
is more suited for electronic music (at some future point), but I kinda like the results. "Vomit of
the Song" &#x1f918;

### Bug fixes

* I fixed a crash when you deleted a node, closed the project and the reopened it.

* When the project fails to open for whatever reason, a dialog just tells you about it and you get
back to the "open project" dialog - instead of completely crashing noisicaä. Again something that
hopefully doesn't happen often for end-users, but is quite frequent during development.

### Internal changes

I slightly changed the file structure for projects. Now each project has a single directory, and all
files are stored in that directory.

And the only significant change I had to make to get the startup process working smoothly was to
reorganize the instrument library. At least on my machine it contains a few thousand entries, and
initializing that list blocked the main thread for a second or so. I reorganized that code such that
the list is now built in smaller chunks. And as a side effect of that reorganization, that work in
only done once instead of every time an instrument library dialog is opened. In QT speak: there's
now a single InstrumentList object, which implements the
[QAbstractItemModel](https://doc.qt.io/qt-5/qabstractitemmodel.html) API, and all
[QTreeView](https://doc.qt.io/qt-5/qtreeview.html) widgets share that model.
