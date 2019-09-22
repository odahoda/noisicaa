Title: PySide2 non-migration
Date: 2019-09-22

I was about to finish another sprint (implementing a saner copy&paste system, as I [hinted
earlier](/blog/2019/09-08-development-update.md)). So I ran `mypy` over the sources and saw that it
complains about a bunch of things, which are caused by an issue with `PyQt5`.

`PyQt5` seems to not like classes, which explicitly inherit from multiple "`Q`" classes.
E.g. something like that:

```python
class SomeMixin(QtCore.QWidget):
    def someMethod(self):
        self.update()

class SomeLineEdit(SomeMixin, QtCore.QLineEdit):
    ...

```

`QLineEdit` is a subclass of `QWidget`, so the above should be perfectly fine. But not for
`PyQt5`. When I tried to make a minimal example, it just segfaulted, but I vaguely remember seeing
some exception being raised. To workaround that, I had to make such mixin classes not inherit from a
"`Q`" class (e.g. just `object`), which is perfectly fine at runtime. But `mypy` has no idea that
this mixin is only used with some kind of `QWidget` and that `self.update()` is a valid method. So I
have to make `mypy` suppress all those false-positive warnings, which makes the code look ugly, and
I lose type checking for any real issues.

Besides that `PyQt5`'s support for type annotations was not so great anyway. I'm maintaining my own
set of stubs for it, which are based on the original `PyQt5` stubs, but with lots of manual tweaks
to make them actually useful.

So when I saw that `Qt` now [officially includes Python
bindings](http://blog.qt.io/blog/2018/12/06/qt-5-12-lts-released/) in the shape of
[`PySide2`](https://wiki.qt.io/Qt_for_Python), I was interested in evaluating a migration. There was
an open [ticket for adding stubs](https://bugreports.qt.io/browse/PYSIDE-735), but that was fixed
for version 5.13.

It's easy to install via `pip`, so I made a quick test to see if `PySide2` was also suffering from
the inheritance issue above. It wasn't, so let's give a real migration a try.

`PySide2` looks sufficiently similar to `PyQt5`, that you could think a simple `s/PyQt5/PySide2/`
might already be enough. For some projects it might already be that, plus some more trivial renames
like `pyqtSignal`&rarr;`Signal` or `pyqtProperty`&rarr;`Property`.

But there are more subtle differences, which make it much harder (at least for noisicaä)...

* The `connect()` method of signals returns a boolean. Apparently it can fail (no idea under which
  conditions...), so you should probably check the return value. Which is very unpythonic - it
  should just raise an exception. And in `PyQt5` it returns a `Connection` instance, which can be
  passed to `disconnect()`. That's the only way to disconnect a `lambda` function (without carrying
  a reference to that function around), which I do a lot, so that's annoying.
* The way how a class level `Signal` attribute gets turned into an instance level `SignalInstance`
  attribute looks odd. In `PyQt5` the `pyqtSignal` implements the property protocol, so accessing
  the attribute on an instance returns the appropriate `pyqtBoundSignal` instance. In `PySide2` the
  metaclass does somehow create a `SignalInstance` for each `Signal` and [injects that into the
  instance's
  `__dict__`](https://code.qt.io/cgit/pyside/pyside-setup.git/tree/sources/pyside2/libpyside/pyside.cpp?h=5.13.1#n313),
  though I haven't really figured out when this actually happens. The problem for me is that there
  doesn't seem to be a way to get from an `Signal` instance and the owning object to the
  `SignalInstance`. Which I do in some helper function, which saves me a lot of boilerplate code. I
  could find a workaround, but that is really ugly... Parsing the `str()` of the `Signal`
  instance... I won't say more. Too embarrassing.
* Signals cannot use [an `Enum` as the type](https://bugreports.qt.io/browse/PYSIDE-239). That bug
  is already 5 years old and for an ancient version of `PySide`. The workaround is to declare those
  signals with type `object` (and lose some type safety).
* `QSettings.value()` does not return the default value, if it is `0` or `False`. That seems like a
  plain and simple bug.

Those are the issues, which I have found so far. At least the unittests are now passing, but that
doesn't really mean that much, because the test coverage for the UI code isn't that great. And
getting there wasn't easy, because `PySide2` is also very crash happy. So instead of a nice Python
exception telling me where and what was wrong, I just got the unhelpful "Segmentation fault (core
dumped)" message. I had to perform the "install from source" dance to get a version with debug
symbols, so `gdb` could at least tell me something about the problem.

And now I'm getting this exception:

```text
Traceback (most recent call last):
  [...]
  File "/home/pink/noisicaa/build/noisicaa/ui/control_value_connector.py", line 62, in __init__
    self.valueChanged.connect(self.__onValueEdited)
TypeError: connect() takes 3 positional arguments but 4 were given
```

Sorry, but that simply does not make sense.

It would have been nice to have a viable alternative to `PyQt5`, and perhaps `PySide2` is that, if
you're starting a new project from scratch. But migrating noisicaä does not seem worth the effort,
at least not now. There is at least some hope that development of `PySide2` gets a boost, at least
for a while, now that it has been included in the `Qt` canon. Let's give it some more time.
