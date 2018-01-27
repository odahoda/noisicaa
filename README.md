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

Follow the development at http://noisicaa.blogspot.com/

License: GPL2 (see file COPYING).

Requirements
------------

This project is currenly only designed to run on Linux desktops. No effort has
yet been made to make it run on anything else than Ubuntu 16.04 and 17.10
(which are the distributions used for development).

Getting Started
---------------

These instructions are not targetted at end users. There are not prebuilt
binary packages, which you could just install, so you have to build from
source. It is assumed that you're moderately experienced with software
development on Linux.

First grab the latest source code:

    git clone https://github.com/odahoda/noisicaa.git
    cd noisicaa
Then install the deb packages that are needed to build and run it:

    sudo apt-get install $(./listdeps --system --build)
For the first time setup, create a new virtualenv:

    python3 -m venv ENV
    . ENV/bin/activate
    pip install --upgrade pip wheel
And populate it with a bunch of python packages that noisicaä uses:

    pip install $(./listdeps --pip --build)
Now you should be ready to build it:

    python3 setup.py build
There is currently no way to install it, so you can only run it from the build
directory using

    bin/noisicaä

Everytime you open a new `bash` to work with it, you have to activate the
virtual environment using

    . ENV/bin/activate
