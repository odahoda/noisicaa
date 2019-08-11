Title: Development update (August 11)
Date: 2019-08-11

And another
[commit](https://github.com/odahoda/noisicaa/commit/53ccc97183a04c96a24c06f1c0eb90a05af6a1fe), which
only improves the development infrastructure, this time focused on testing.

### `./waf test`

I removed the `bin/runtests` script, which collects and runs all tests, and moved that logic into
`waf`, so tests are now run with the command `./waf test`. The main benefit is that I'm getting
parallel execution almost, but not quite, for free.

The drawbacks are:

* Each test module is executed in a subprocess, which causes some overhead. That's specifically
  noticeable for the unittests, where the tests themselves are fast and thus the overhead matters
  more.
* `pylint` is now also run as a subprocess. `runtests.py` imported it as a `python` module and
  subsequent `pylint` runs could use previously cached data.
* I needed some additional code to store the results of each tests and merge them at the end. For
  the unittests I'm using
  [`unittest-xml-reporting`](https://pypi.org/project/unittest-xml-reporting/) to write them out as
  XML and [`xunitparser`](https://pypi.org/project/xunitparser/) to read them back. For `mypy` and
  `pylint` I'm just writing/reading plain text files.
* `mypy` needed some extra care, because running multiple `mypy` processes using the same cache
  directory causes some race conditions. I have to use a pool of caches, so each cache is only used
  by one `mypy` process at a time.

But overall the test suite now runs about twice as fast. Some unscientific benchmarks:

| command                      | runtime |
| :--------------------------- | ------: |
| `bin/runtests`               |   15:49 |
| `./waf test -j8`             |    7:16 |
| `./waf test -j4`             |    8:36 |
| `./waf test -j2`             |   13:58 |
| `./waf test -j1`             |   26:31 |
| `bin/runtests --tags=unit`   |    0:42 |
| `./waf test -j8 --tags=unit` |    0:23 |
| `./waf test -j4 --tags=unit` |    0:30 |
| `./waf test -j2 --tags=unit` |    0:51 |
| `./waf test -j1 --tags=unit` |    1:35 |

I just used a single run of each command and `/usr/bin/time` for the measurement.

The overhead is about 2x, so you need two cores just to make of for it. Which means that you're
penalized, if you are attempting to do noisicaä development on a single core machine. But I guess
using a single core machine (which must be pretty old) isn't much fun anyway these days.

What is interesting is that there is little gained when going from four to eight cores. That's
probably because my CPU is a quad-core with 2x hyper-threading, but I haven't looked into that issue
any deeper.

Another advantage of running tests in subprocesses is that I can now put a timeout on tests, so if
some test hangs, it will eventually fail and I don't have to kill the main process, thus losing the
actual test report.

### VM Tests

I reanimated the VM tests, which suffered from some bitrot and didn't work anymore. While at it, I
switched from `virtualbox` to `qemu` for the VM, because `qemu` is a bit easier to automate.

These tests launch a VM with a minimal installation of the OS (current only Ubuntu 16.04 and 18.04)
and then build noisicaä from the sources. This is mostly to verify that all dependencies are
correctly declared and the build instructions work as advertised on a system that isn't my
development system.

Once I got the tests working again, they uncovered some bitrot, which caused noisicaä to not work
anymore on Ubuntu 16.04 or Python 3.5.

### `clang-tidy`

The test suite now runs `clang-tidy` over `C++` source files. I previously cranked up the pickiness
of `gcc` (i.e. `-Werror -pedantic`), but that meant that compilation would fail for every minor
issue. Now building became more "pythonic": `C++` source get built, as long as there are no major
issues (with all warnings disabled, i.e. `-w`), and once I want to also have the code "clean" I run
`clang-tidy` over it.

I haven't verified, if the issues that `gcc` would have detected are all covered by
`clang-tidy`. I'm just assuming that `clang-tidy` is "good enough". I also have not yet attempted to
fine tune `clang-tidy` and run it with default settings for now.

### Upgraded `mypy` to 0.720

That version specifically has a new option `warn_unused_ignores`, so I could find and remove
overrides, which used to fix false-positives in some previous version of `mypy`, but were now
obsolete and potentially masked some real issues.

### Removed all build noise

At least with my setup, all random noise generated during the build steps has been removed.
