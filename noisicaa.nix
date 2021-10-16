# @begin:license
#
# Copyright (c) 2015-2021, Ben Niemann <pink@odahoda.de>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# @end:license

{ lib
, stdenv
, fetchFromGitHub
, python3
, wafHook
}:
let
  gitignoreSrc = fetchFromGitHub {
    owner = "hercules-ci";
    repo = "gitignore.nix";
    rev = "9e80c4d83026fa6548bc53b1a6fab8549a6991f6";  # 2021-10-16
    sha256 = "sha256:04n9chlpbifgc5pa3zx6ff3rji9am6msrbn1z3x1iinjz2xjfp4p";
  };
  inherit (import gitignoreSrc { inherit lib; }) gitignoreSource;
in stdenv.mkDerivation {
  pname = "noisicaa";
  version = "0.1";

  src = gitignoreSource ./.;

  nativeBuildInputs = [
    python3
    wafHook
  ];
}
