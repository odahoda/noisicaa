# @custom_license
#
# Based on local_rpath.py from waf's extras dir.
# Original URL: https://gitlab.com/ita1024/waf/blob/master/waflib/extras/local_rpath.py
# Original License: BSD License


import copy
from waflib.TaskGen import after_method, feature
from waflib.Errors import WafError


@after_method('propagate_uselib_vars')
@feature('cprogram', 'cshlib', 'cxxprogram', 'cxxshlib', 'fcprogram', 'fcshlib')
def add_rpath_stuff(self):
    all_uses = copy.copy(self.to_list(getattr(self, 'use', [])))
    while all_uses:
        name = all_uses.pop()
        try:
            tg = self.bld.get_tgen_by_name(name)
        except WafError:
            continue
        if hasattr(tg, 'link_task'):
            self.env.append_value('RPATH', tg.link_task.outputs[0].parent.abspath())
            all_uses.extend(self.to_list(getattr(tg, 'use', [])))
