# -*- mode: python -*-

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

import importlib.util
import os.path
import py_compile
import re
import shutil
import subprocess

from waflib.Configure import conf
from waflib.Task import Task
from waflib.TaskGen import before_method, after_method, feature
from waflib import Utils


def _fix_args(ctx, *, source, **kwargs):
    kwargs['source'] = [
        ctx.path.make_node(src) for src in Utils.to_list(source)]

    if 'target' not in kwargs:
       kwargs['target'] = kwargs['source'][0].get_bld().change_ext('.so')

    if 'use' in kwargs:
        kwargs['use'] = Utils.to_list(kwargs['use'])

    return kwargs


@conf
def ladspa_plugin(ctx, **kwargs):
    kwargs = _fix_args(ctx, **kwargs)
    ctx.shlib(**kwargs)


@conf
def lv2_plugin(ctx, **kwargs):
    kwargs = _fix_args(ctx, **kwargs)
    ctx.shlib(**kwargs)

    ctx.static_file('manifest.ttl')
    ctx.static_file(kwargs['target'].change_ext('.ttl').get_src())


@conf
def lv2_plugin_ui(ctx, **kwargs):
    kwargs = _fix_args(ctx, **kwargs)
    ctx.shlib(**kwargs)
