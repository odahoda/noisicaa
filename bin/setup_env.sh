#!/bin/bash

if [ -z "$VIRTUAL_ENV" -o ! -d "$VIRTUAL_ENV" ]; then
    echo >&2 "Not running in a virtualenv. Please set that up first."
    exit 1
fi

BASEDIR=$(readlink -f "$(dirname "$0")/..")
LIBSDIR="$BASEDIR/libs"

LILV_DEPS="libserd-dev libsord-dev libsratom-dev lv2-examples"
LADSPA_DEPS="ladspa-sdk"
CSOUND_DEPS="libsndfile1-dev libsamplerate0-dev libboost-dev flex bison cmake"
CAPNP_DEPS="capnproto libcapnp-0.5.3"

PYVERSION=3.5

PACKAGES_QT5="python3-pyqt5 python3-pyqt5.qtsvg"

PACKAGES="python$PYVERSION python$PYVERSION-venv python$PYVERSION-dev libxml2-dev libxslt1-dev portaudio19-dev libavutil-dev libavutil-ffmpeg54 libswresample-dev libswresample-ffmpeg1 libfluidsynth1 libfluidsynth-dev inkscape timgm6mb-soundfont fluid-soundfont-gs fluid-soundfont-gm flac zlib1g-dev $PACKAGES_QT5 $CSOUND_DEPS $LADSPA_DEPS $LILV_DEPS $CAPNP_DEPS"

function pkg-status() {
    PKG="$1"
    (
        dpkg-query -W -f='${Status}\n' "$PKG" 2>/dev/null || echo "foo bar not-installed"
    ) | awk '{print $3}'
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

    ############################################################################
    # install libraries

    pip install --upgrade pip
    pip install --upgrade -r $BASEDIR/requirements.txt
}

main
