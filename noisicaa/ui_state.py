#!/usr/bin/python3

import logging
import base64

# from noisicaa.music import commands
# from noisicaa.music import state
# from noisicaa.core import model_base

# logger = logging.getLogger(__name__)


# class UpdateUIState(commands.Command):
#     args = model_base.DictProperty()

#     def __init__(self, state=None, **kwargs):
#         super().__init__(state=state)
#         if state is None:
#             self.args.update(kwargs)

#     def __str__(self):
#         return '%s{%s}' % (
#             super().__str__(),
#             ', '.join('%s=%r' % (k, v) for k, v in sorted(self.args.items())))

#     def run(self, state):
#         changes = {}
#         for key, value in self.args.items():
#             if value is not None:
#                 if isinstance(value, bytes):
#                     tvalue = (
#                         'bytes', base64.b85encode(value).decode('ascii'))
#                 else:
#                     assert isinstance(value, (bool, int, float, str))
#                     tvalue = (type(value).__name__, value)

#                 if key not in state.ui_state or state.ui_state[key] != tvalue:
#                     logger.info(
#                         "UIState.%s: %s -> %r",
#                         key,
#                         (repr(state.ui_state[key])
#                          if key in state.ui_state else "<undefined>"),
#                         value)
#                     changes[key] = value
#                 state.ui_state[key] = tvalue

#         if changes:
#             for listener in state.change_listeners:
#                 listener(changes)

# commands.Command.register_subclass(UpdateUIState)


# class UIState(state.StateBase):
#     ui_state = model_base.DictProperty()

#     def __init__(self, state=None):
#         super().__init__(state)

#         self.change_listeners = []

#     def get(self, key, default):
#         vtype, value = self.ui_state.get(key, ('NoneType', None))
#         if value is None:
#             return default
#         if vtype == 'bytes':
#             return base64.b85decode(value.encode('ascii'))
#         return value

#     def add_change_listener(self, listener):
#         self.change_listeners.append(listener)
