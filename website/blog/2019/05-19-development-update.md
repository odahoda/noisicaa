Title: Development update (May 19)
Date: 2019-05-19

The great "Model Merge" refactoring, which I described in the [previous post](04-28-model-merge) has
been
[committed](https://github.com/odahoda/noisicaa/commit/accff25ed0495d14a793f5d5acbec6158b1a1afa).

Overall it was mostly painless and worked the way I planned. In the beginning it felt a bit like a
massacre as I was tearing down a lot of code, and the whole thing was in some messy intermediate
state, but quickly new patterns emerged and the conversion became mostly
mechanical. [mypy](http://mypy-lang.org/) and [pylint](https://www.pylint.org/) were very helpful
tools during this adventure. I basically went from one file to the next, fixing all the issues that
they complained about and at the end, when all pieces fell into place and I had something executable
again, there were just very few bugs left - I think just one issue, which was detected by a unittest
and one or two issues I found through manual testing. The biggest advantage of those tools over
unittests alone is that they produce meaningful reports for a single file even if the code at large
isn't in a usable state. I had to refactor a lot of code in different places before I could even get
any passing unittests and without mypy/pylint I would have been flying blind for that time.

After I executed my plan, I had took another stab at the idea of auto-generating some of the
boilerplate code for model classes. I tried it once before, but abandoned it again, because it
turned out to be too complicated. But with the new, much simpler code structure after the
refactoring, it became much easier to do. That got rid of another batch of "boring" code and adding
new classes (e.g. for more builtin node types) should now be much less cumbersome than it was
before.

According to [SLOCCount](https://dwheeler.com/sloccount/) the total code base shrank by
approximately 3000 source lines of code or 6% (or almost 8% when just looking at the Python code),
which is quite considerable.

With this project out of the way (and out of my head), I should do some "shiny new features" sprint
next.
