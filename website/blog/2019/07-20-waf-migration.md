Title: waf migration
Date: 2019-07-20

I could not resist and spent the last few days converting the build system from
[`cmake`](https://cmake.org/) to [`waf`](https://waf.io/).

Surprisingly the resulting
[commit](https://github.com/odahoda/noisicaa/commit/0e4c0ddf10143d768de71eb76ce81417db8a2411) has a
negative line count, even though the new system has some new features.

I was never really happy with `cmake`. I needed a proper build system, because noisicaä isn't a pure
`python` application (which most of the other things are, that I do in my spare time). For the
initial prototype I got away with using `setup.py` to build the few `cython` extensions, but I
quickly grew out of that. My usual choice would have been good, old
[`make`](https://www.gnu.org/software/make/), but one of the common patterns of noisicaä development
is to upgrade my toolbox and try something more modern. `cmake` advertises itself as modern, fast
and flexible, and it's used by a lot of large open source projects. So I decided to give it a try.

And it's certainly easy to use for `c++` projects - everything needed for that is
built-in. But my case involved a mix of `python`, `cython` as well as a bunch of custom build rules
to auto generate various files, e.g. using `csound`, `faust`, etc. To define such custom build
rules, you have to dive deep into `cmake`'s language and that's the part that turned me off.

`cmake`'s language feels like a reanimated corpse that dies a few decades ago. It's a macro
language, there are no proper functions, so "return values" are written to some kinda global
variables. While you can get everything done somehow, it feels really quirky.

Also `cmake`'s distinction between files and targets was very confusing to me. Only target can have
dependencies on other targets - at least that's how I understood it. I could never really wrap my
head around it, so I have probably created a lot more targets than necessary.

`waf` is not without it's own quirks. Part of that might be due to compatibility requirements. On
the one hand compatibility with older versions of `waf`, i.e. the usual accumulation of cruft that
you see in any non-trivial application. On the other hand compatibility with old `python`
version. E.g. `waf`'s `Node` class looks a lot like
[`pathlib`](https://docs.python.org/3/library/pathlib.html), but it cannot use it as long as it
wants to stay compatible with `python` versions before 3.4. And because it wants to be both self
contained and small, it can't just use packages outside of the `stdlib`.

But the biggest selling point of `waf` is that it's `python`. Instead of some half baked custom
language, you have the full power of a proper general purpose language at your fingertips.

Converting the existing build logic over to `waf` was pretty painless. Basically just rename all
[`CMakeLists.txt`](https://github.com/odahoda/noisicaa/blob/371337a0/noisicaa/core/CMakeLists.txt)
files to [`wscript`](https://github.com/odahoda/noisicaa/blob/0e4c0ddf/noisicaa/core/wscript) and
make some fairly mechanical syntax changes. Most of the work was reimplementing the various custom
rules to `waf`. That turned out to be a bit more
[verbose](https://github.com/odahoda/noisicaa/tree/0e4c0ddf/build_utils/waf) in terms of line count,
but that's more than compensated just by expressing the logic in a proper programming language.

The only significant difference should be that I never got dependencies of `cython` modules right in
`cmake`. Every once in a while I made a change that should have triggered a rebuild of some `cython`
modules, but that never happened - resulting in runtime errors. Getting that right in `waf` was very
straight forward.

Once I did the basic build logic carried over to `waf`, I started looking into things I could do
better now.

### Handling of 3rd party dependencies

One of the things that neither `cmake` nor `waf` (nor any other build system that I know of)
directly support, is the handling of dependencies on 3rd party packages. That's actually something
that could be done with `setup.py`, which is more of a package management system than a build
system - at least for other `python` packages (and with a terrible hack, also for non-`python`
libraries).

Before you can start to build any software from source, you probably need a bunch of libraries,
packages, tools, etc. installed, which are used by those sources. Usually the `configure` step of
the build system checks for these dependencies and fails if anything is missing. It is then left to
the user, possibly directed by some `INSTALL` documentation, to install the missing pieces and try
again. That usually takes a few iterations until everything is in place. That's pretty tedious for
the user, and it's hard to keep the documentation in sync with the actual requirements of the
software.

I used to have a [`listdeps`](https://github.com/odahoda/noisicaa/blob/371337a0/listdeps) script,
which had all the knowledge about required packages, both `python` packages that are to be installed
with `pip`, as well as system packages to be installed with `apt`. This way the list of required
packages was encoded in a way that did not need human intelligence to decipher. I have fully
automated [tests](https://github.com/odahoda/noisicaa/blob/0e4c0ddf/noisidev/runvmtests.py), which
perform the installation on a minimal system (running in a VM), thus ensuring that the list of
requirements is complete.

I now took this approach a step further and integrated it directly into `waf configure`. So `waf`
checks if all required packages are present and if not, simply installs them. `python` packages are
downloaded and installed in a virtual environment. System packages are installed with `apt`, which
might trigger a password prompt. Usually the user does not expect `configure` to actually modify the
system, so that behavior must be enabled by some flags.

There were a few dependencies (e.g. `csound`, `protoc`, ...), which are not available as easily
installable packages - usually because I want a newer version that what is available in Ubuntu. For
those packages I used that terrible hack I mentioned above. For each such dependency I had a
[`setup.py`](https://github.com/odahoda/noisicaa/blob/371337a0/3rdparty/csound/setup.py) file, which
I could install with `pip`. But instead of having any real sources of its own, those `setup.py`
scripts just had the logic to download, build and install the sources of those packages into the
virtual environment. I have now moved that logic directly into
[`waf`](https://github.com/odahoda/noisicaa/blob/0e4c0ddf/build_utils/waf/virtenv.py#L651), but
apart from that I'm following the same approach: instead of documenting that you should download and
install library X at version Y, the build system just does it itself.

### Transparent virtual environment handling

As usual for `python` projects, I'm using a virtual environment to locally install 3rd party
`python` packages. And I go one step further and also install locally built versions of `csound`,
`protoc`, etc. there as mentioned above.

The normal process is to first "activate" the virtual environment, so these packages become visible
to `python`.

I now moved the management of the virtual environment into `waf`, so it becomes completely
transparent to the user. It is
[created](https://github.com/odahoda/noisicaa/blob/0e4c0ddf/build_utils/waf/virtenv.py#L278) and
[populated](https://github.com/odahoda/noisicaa/blob/0e4c0ddf/build_utils/waf/virtenv.py#L144) by
`waf configure` and automatically activated by subsequent uses of
[`waf`](https://github.com/odahoda/noisicaa/blob/0e4c0ddf/wscript#L35) or when running
[noisicaä](https://github.com/odahoda/noisicaa/blob/0e4c0ddf/bin/noisica%C3%A4#L28) from the build
directory.

### `waf install`

Just out of curiosity I tried out what happens when I run `waf install`. And it turned out that the
changes to get that work correctly weren't that difficult. The trickiest part was again dealing with
those 3rd party packages. For noisicaä to work, it needs those packages and libraries installed with
its own files. I ended up just
[copying](https://github.com/odahoda/noisicaa/blob/0e4c0ddf/build_utils/waf/install.py#L57) those
files from the virtual environment into the target `lib` directory.
