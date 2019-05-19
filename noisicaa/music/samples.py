#!/usr/bin/python3

# @begin:license
#
# Copyright (c) 2015-2019, Benjamin Niemann <pink@odahoda.de>
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

import logging
from typing import Any, Optional

from noisicaa.bindings import sndfile
from . import model_base
from . import _model

logger = logging.getLogger(__name__)


class Sample(_model.Sample, model_base.ProjectChild):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.__samples = None  # type: memoryview

    def create(self, *, path: Optional[str] = None, **kwargs: Any) -> None:
        super().create(**kwargs)

        self.path = path

    @property
    def samples(self) -> memoryview:
        if self.__samples is None:
            with sndfile.SndFile(self.path) as sf:
                self.__samples = sf.get_samples()
        return self.__samples
