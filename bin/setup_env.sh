#!/bin/bash

DEST=$(readlink -f "$(dirname "$0")/ENV")
BUILDDIR=/tmp/build
LIBSDIR=$(readlink -f "$(dirname "$0")/../libs")

#LILV_DEPS="lv2-dev libserd-dev libsord-dev libsratom-dev swig"
#LADSPA_DEPS="cython3 ladspa-sdk"

PYVERSION=3.4
SIPVERSION=4.16.9
PYQTVERSION=5.5

PACKAGES="python$PYVERSION python$PYVERSION-venv python$PYVERSION-dev qt5-qmake qtbase5-dev sip-dev libxml2-dev libxslt1-dev portaudio19-dev"

function pkg-status() {
    PKG="$1"
    (
        dpkg-query -W -f='${Status}\n' "$PKG" 2>/dev/null || echo "foo bar not-installed"
    ) | awk '{print $3}'
}

function install-sip() {
    cd $BUILDDIR
    tar xzf $LIBSDIR/sip-$SIPVERSION.tar.gz
    cd sip-$SIPVERSION
    python3 configure.py --incdir=$DEST/include
    make -j8
    make install
}

function install-pyqt() {
    cd $BUILDDIR
    tar xzf $LIBSDIR/PyQt-gpl-$PYQTVERSION.tar.gz
    cd PyQt-gpl-$PYQTVERSION
    python3 configure.py --qmake=/usr/lib/x86_64-linux-gnu/qt5/bin/qmake --sip-incdir=$DEST/include --verbose --confirm-license
    make -j8
    make install
}

function main() {
    ############################################################################
    # check prerequisites

    declare -a MISSING
    for PKG in $PACKAGES; do
	STATUS=
	if [ "$(pkg-status "$PKG")" != "installed" ]; then
            MISSING+=( "$PKG" )
	fi
    done

    if [ ${#MISSING[@]} -gt 0 ]; then
	echo >&2 "Missing some packages: ${MISSING[@]}"
	exit 1
    fi

    set -ex

    ############################################################################
    # setup environment

    pyvenv-$PYVERSION --clear "$DEST"
    . "$DEST/bin/activate"

    ############################################################################
    # install libraries

    rm -fr $BUILDDIR
    mkdir -p $BUILDDIR

    install-sip
    install-pyqt
    pip install pylint
    pip install coverage
    pip install lxml
    pip install cssutils
    pip install numpy
    pip install cython
    pip install pyfakefs
    pip install mox3
    pip install portalocker
    pip install toposort
    pip install pyaudio
}

main
