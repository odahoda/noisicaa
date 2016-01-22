#!/bin/bash

if [ -z "$VIRTUAL_ENV" -o ! -d "$VIRTUAL_ENV" ]; then
    echo >&2 "Not running in a virtualenv. Please set that up first"
    exit 1
fi

BUILDDIR="$VIRTUAL_ENV/build"
BASEDIR=$(readlink -f "$(dirname "$0")/..")
LIBSDIR="$BASEDIR/libs"

#LILV_DEPS="lv2-dev libserd-dev libsord-dev libsratom-dev swig"
#LADSPA_DEPS="cython3 ladspa-sdk"

PYVERSION=3.4
SIPVERSION=4.17
PYQTVERSION=5.5.1

PACKAGES="python$PYVERSION python$PYVERSION-venv python$PYVERSION-dev qt5-qmake qtbase5-dev sip-dev libxml2-dev libxslt1-dev portaudio19-dev libavutil-dev libavutil-ffmpeg54 libswresample-dev libswresample-ffmpeg1 libfluidsynth1 libfluidsynth-dev libqt5svg5-dev inkscape timgm6mb-soundfont fluid-soundfont-gs fluid-soundfont-gm flac"

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
    python3 configure.py --incdir=$VIRTUAL_ENV/include
    make -j8
    make install
}

function install-pyqt() {
    cd $BUILDDIR
    tar xzf $LIBSDIR/PyQt-gpl-$PYQTVERSION.tar.gz
    cd PyQt-gpl-$PYQTVERSION
    python3 configure.py --qmake=/usr/lib/x86_64-linux-gnu/qt5/bin/qmake --sip-incdir=$VIRTUAL_ENV/include --verbose --confirm-license
    make -j8
    make install
}

function main() {
    set -e

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

    if [ ! -f $LIBSDIR/sip-$SIPVERSION.tar.gz ]; then
	wget -O$LIBSDIR/sip-$SIPVERSION.tar.gz http://sourceforge.net/projects/pyqt/files/sip/sip-$SIPVERSION/sip-$SIPVERSION.tar.gz
    fi

    if [ ! -f $LIBSDIR/PyQt-gpl-$PYQTVERSION.tar.gz ]; then
	wget -O$LIBSDIR/PyQt-gpl-$PYQTVERSION.tar.gz http://sourceforge.net/projects/pyqt/files/PyQt5/PyQt-$PYQTVERSION/PyQt-gpl-$PYQTVERSION.tar.gz
    fi

    ############################################################################
    # install libraries

    rm -fr $BUILDDIR
    mkdir -p $BUILDDIR

    install-sip
    install-pyqt
    pip install --upgrade -r $BASEDIR/requirements.txt
}

main
