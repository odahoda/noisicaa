**This repository is archived. The code is now hosted at https://git.odahoda.de/pink/noisicaa**


noisicaä
========

**Important note**: This is project is in pre-APLHA  state, do not expect it to
be usable in any form or shape.

* It has bugs.
* It does not do a lot of useful things.
* There is no documentation.
* And most importantly: the save format is not finalized and will change in
  incompatible ways, i.e. you will not be able to open your work from older
  versions.


What's This?
------------

A simple music editor with a focus on classical musical notation.

Follow the development at http://noisicaa.odahoda.de/

License: GPL2 (see file COPYING).

Requirements
------------

This project is currenly only designed to run on Linux desktops. No effort has
yet been made to make it run on anything else than Ubuntu 16.04 and 18.04
(which are the distributions used for development).

Getting Started
---------------

These instructions are not targetted at end users. There are not prebuilt
binary packages, which you could just install, so you have to build from
source. It is assumed that you're moderately experienced with software
development on Linux.

You need at least `git` and `python3` installed on your system.

    sudo apt install git python3

First grab the latest source code:

    git clone https://github.com/odahoda/noisicaa.git
    cd noisicaa

Configure the project. This will create a virtual environment and populate it
with the required 3rd party packages. It will also install missing system
packages - this assumes that you have `sudo` rights on the system, and it might
query you for your password.

    ./waf configure --download --install-system-packages

Now you can build it:

    ./waf build

You can either run it from the build directory:

    bin/noisicaä

Or install it to `/usr/local`:

    sudo ./waf install
