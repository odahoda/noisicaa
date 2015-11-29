noisicaä
========

**Important note**: This is project is in pre-APLHA  state, do not expect it to
be usable in any form or shape.

* It contains bugs.
* It does not do a lot of useful things.
* There is no documentation.
* Even getting it to run is difficult and undocumented.
* And most importantly: the save format is not finalized and will change in
  incompatible ways, i.e. you will not be able to open your work from older
  versions.


What's This?
------------

A simple music editor with a focus on classical musical notation.

Follow the development at http://noisicaa.blogspot.com/

License: GPL2 (see file COPYING).

Requirements
------------

This project is currenly only designed to run on Linux desktops. No effort has
yet been made to make it run on anything else than the latest Ubuntu release
(15.10 at the time of writing).

Getting Started
---------------

These instructions are not targetted at end users. It is assumed that you're
moderately experienced with software development on Linux.

For the first time setup, run

    bin/setup_env.sh
It will probably fail and ask you to install some additional packages and
download some files into `libs/` (be careful to use the exact versions that it's
asking for). Try again, until it is happy and starts compiling stuff.

Then (and everytime you open a new `bash` to work with it) activate the
virtual environment using

    . ENV/bin/activate

And finally run

    bin/noisicaä --dev-mode
