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

import random
import re
from typing import List

from . import data


class TitleGenerator(object):
    def __init__(self, seed: int = None) -> None:
        self.__rnd = random.Random(seed)

    def __pick(self, lst: List[str]) -> str:
        return self.__rnd.choice(lst)

    def generate(self) -> str:
        sentence = self.__pick(data.sentence)

        while True:
            n_sentence = re.sub(
                r'\${([^}]+)}',
                lambda m: self.__pick(data.word_sets[m.group(1)]),
                sentence)
            if n_sentence == sentence:
                break
            sentence = n_sentence

        sentence = sentence.replace("**", "The ")
        sentence = sentence.replace("*", "")

        return sentence
