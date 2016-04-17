#!/bin/bash

if [ -z "$VIRTUAL_ENV" -o ! -d "$VIRTUAL_ENV" ]; then
    echo >&2 "Not running in a virtualenv. Please set that up first."
    exit 1
fi

BASEDIR=$(readlink -f "$(dirname "$0")/..")
LIBSDIR="$BASEDIR/libs"

#LILV_DEPS="lv2-dev libserd-dev libsord-dev libsratom-dev swig"
#LADSPA_DEPS="cython3 ladspa-sdk"

PYVERSION=3.4

PACKAGES_QT5="python3-pyqt5 python3-pyqt5.qtsvg"

PACKAGES="python$PYVERSION python$PYVERSION-venv python$PYVERSION-dev libxml2-dev libxslt1-dev portaudio19-dev libavutil-dev libavutil-ffmpeg54 libswresample-dev libswresample-ffmpeg1 libfluidsynth1 libfluidsynth-dev inkscape timgm6mb-soundfont fluid-soundfont-gs fluid-soundfont-gm flac $PACKAGES_QT5"

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
