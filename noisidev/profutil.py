#!/usr/bin/python3

import contextlib
import cProfile
import os.path
import tempfile

from noisicaa import constants

def profile(file_base, func):
    if not constants.TEST_OPTS.ENABLE_PROFILER:
        return func()

    profiler = cProfile.Profile()
    ret = profiler.runcall(func)
    profile_path = os.path.join(
        tempfile.gettempdir(), file_base + '.prof')
    profiler.dump_stats(profile_path)
    print('Profile written to %s' % profile_path)
    return ret

def profile_method(func):
    def _wrapped(self):
        return profile(self.id(), lambda: func(self))

    return _wrapped
