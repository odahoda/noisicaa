# @begin:license
#
# Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
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

import asyncio
import collections
import datetime
import heapq
import itertools
import os
import signal
import textwrap
import unicodedata
from typing import (  # pylint: disable=unused-import
    Any, Optional, Awaitable, Callable, Iterable, Iterator, Dict, List, Set, Tuple, Union
)

import psutil
import urwid

from noisicaa import core
from noisicaa import logging

logger = logging.getLogger(__name__)


ARROW_DOWN = unicodedata.lookup('Black Down-Pointing Triangle')
ARROW_UP = unicodedata.lookup('Black Up-Pointing Triangle')
ARROW_LEFT = unicodedata.lookup('Black Left-Pointing Triangle')
ARROW_RIGHT = unicodedata.lookup('Black Right-Pointing Triangle')


class ProcessInfo(object):
    def __init__(self, pid: int, name: str) -> None:
        self.pid = pid
        self.name = name

        self.__info = psutil.Process(pid)

        self.mem_virt = None  # type: int
        self.mem_res = None  # type: int
        self.mem_shr = None  # type: int
        self.cpu = None  # type: float

    def update(self) -> None:
        with self.__info.oneshot():
            self.cpu = self.__info.cpu_percent()
            mem = self.__info.memory_info()
            self.mem_virt = mem.vms
            self.mem_res = mem.rss
            self.mem_shr = mem.shared


Column = collections.namedtuple('Column', ['align', 'title', 'key_func', 'display_func', 'width'])

process_list_columns = [
    Column(
        align='>',
        title='PID',
        key_func=lambda proc: proc.pid,
        display_func=lambda proc: '%5d' % proc.pid,
        width=5),
    Column(
        align='>',
        title='VIRT',
        key_func=lambda proc: proc.mem_virt,
        display_func=lambda proc: '%8.1f' % (proc.mem_virt / 2**20),
        width=8),
    Column(
        align='>',
        title='RES',
        key_func=lambda proc: proc.mem_res,
        display_func=lambda proc: '%8.1f' % (proc.mem_res / 2**20),
        width=8),
    Column(
        align='>',
        title='SHR',
        key_func=lambda proc: proc.mem_shr,
        display_func=lambda proc: '%8.1f' % (proc.mem_shr / 2**20),
        width=8),
    Column(
        align='>',
        title='CPU',
        key_func=lambda proc: proc.cpu,
        display_func=lambda proc: '%6.1f%%' % proc.cpu,
        width=7),
    Column(
        align='<',
        title='NAME',
        key_func=lambda proc: proc.name,
        display_func=lambda proc: proc.name,
        width=40),
]
process_key_funcs = {col.title: col.key_func for col in process_list_columns}


class TitleBar(urwid.Widget):
    _sizing = frozenset(['box'])
    _selectable = False
    ignore_focus = True

    def __init__(self, event_loop: asyncio.AbstractEventLoop) -> None:
        super().__init__()

        self.__event_loop = event_loop

        self.__started = datetime.datetime.now()

        self.__quit = asyncio.Event(loop=self.__event_loop)
        self.__update_task = self.__event_loop.create_task(self.__update_main())

    async def cleanup(self) -> None:
        self.__quit.set()
        await asyncio.wait_for(self.__update_task, None, loop=self.__event_loop)
        self.__update_task.result()

    async def __update_main(self) -> None:
        while not self.__quit.is_set():
            self._invalidate()

            wait_tasks = [
                asyncio.sleep(1.0, loop=self.__event_loop),
                self.__quit.wait(),
            ]  # type: List[Awaitable]
            _, pending = await asyncio.wait(
                wait_tasks, loop=self.__event_loop, return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()

    def render(self, size: Tuple[int, ...], focus: bool = False) -> urwid.TextCanvas:
        cols, = size

        time_running = datetime.timedelta(
            seconds=int((datetime.datetime.now() - self.__started).total_seconds()))

        title_left = '= noisicaä '
        title_right = ' running for %s == press [h] for help =' % time_running
        min_width = len(title_left) + len(title_right)
        if min_width < cols:
            title = title_left + '=' * (cols - min_width) + title_right
        else:
            title = '=' * cols
        assert len(title) == cols

        text, cs = urwid.apply_target_encoding(title)
        return urwid.TextCanvas([text], [[('title', cols + 1)]], [cs])

    def rows(self, size: Tuple[int, ...], focus: bool = False) -> int:
        return 1

    def keypress(self, size: Tuple[int, ...], key: str) -> Optional[str]:
        return key


class Popup(urwid.WidgetWrap):
    signals = ['close']

    @property
    def size(self) -> Tuple[int, int]:
        raise NotImplementedError

    def keypress(self, size: Tuple[int, ...], key: str) -> Optional[str]:
        if key == 'esc':
            self._emit('close')
            return None

        return key


class HelpPopup(Popup):
    def __init__(self) -> None:
        header_text = textwrap.dedent("""\
            noisicaä
            https://github.com/odahoda/noisicaa
            Copyright (c) 2015-2018, Benjamin Niemann <pink@odahoda.de>
        """)
        header = urwid.Text(header_text, align='center')

        main_text = textwrap.dedent("""\
            h - Show this window
            q - Quit debug console (but not noisicaä)

            Process list
              k - Send SIGTERM to selected process
              K - Send SIGKILL to selected process
              s - Change sort column
              d - Change sort direction
              p - Toggle periodic updates
              space - Update list
        """)
        main = urwid.Text(main_text, align='left')

        body = urwid.Pile([header, main])
        body = urwid.Padding(body, left=1, right=1)
        body = urwid.Filler(body, valign='top', top=1)
        body = urwid.LineBox(body, title='Help (press ESC to close)')
        body = urwid.AttrWrap(body, 'popup')
        super().__init__(body)

    @property
    def size(self) -> Tuple[int, int]:
        return (70, 20)


class Window(urwid.WidgetWrap):
    def __init__(self, title: str, body: urwid.Widget) -> None:
        self.__title = urwid.Text(ARROW_RIGHT + ' ' + title)

        contents = urwid.Pile([
            ('pack', urwid.AttrMap(self.__title, 'windowtitle')),
            body
        ])
        super().__init__(contents)

        self.__body = body


class Dialog(urwid.WidgetWrap):
    signals = ['close']

    def __init__(self, title: str, body: urwid.Widget) -> None:
        body = urwid.LineBox(body, title=title)
        body = urwid.AttrWrap(body, 'popup')
        super().__init__(body)

    @property
    def size(self) -> Tuple[int, int]:
        raise NotImplementedError

    def keypress(self, size: Tuple[int, ...], key: str) -> Optional[str]:
        if key == 'esc':
            self._emit('close')
            return None

        return super().keypress(size, key)  # pylint: disable=not-callable


class DialogHostMixin(urwid.Widget):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.__dialog = None  # type: Optional[Dialog]

    def show_dialog(self, dialog: Dialog) -> None:
        assert self.__dialog is None
        self.__dialog = dialog
        self._invalidate()

    def hide_dialog(self) -> None:
        self.__dialog = None
        self._invalidate()

    def render(self, size: Tuple[int, ...], focus: bool = False) -> urwid.Canvas:
        canv = super().render(size, focus)

        if self.__dialog is not None:
            canv = urwid.CompositeCanvas(canv)

            width, height = size
            dwidth, dheight = self.__dialog.size
            canv.set_pop_up(
                self.__dialog,
                left=(width - dwidth) // 2,
                top=(height - dheight) // 2,
                overlay_width=dwidth,
                overlay_height=dheight)

        return canv


class SignalDialog(Dialog):
    def __init__(self, pid: int) -> None:
        self.__signals = [
            ('TERM', signal.SIGTERM),
            ('KILL', signal.SIGKILL),
            ('ABRT', signal.SIGABRT),
            ('STOP', signal.SIGSTOP),
            ('CONT', signal.SIGCONT),
        ]

        cancel_button = urwid.Button("Cancel")
        urwid.connect_signal(cancel_button, 'click', lambda button: self._emit('close'))

        signal_buttons = []
        for name, sig in self.__signals:
            button = urwid.Button('%s (%d)' % (name, sig.value))  # pylint: disable=no-member
            urwid.connect_signal(button, 'click', lambda button, sig=sig: self.__send_signal(sig))
            signal_buttons.append(button)

        pile = urwid.Pile(signal_buttons + [urwid.Divider(), cancel_button])

        fill = urwid.Filler(pile)
        super().__init__("Send signal to PID=%d" % pid, fill)

        self.__pid = pid

    @property
    def size(self) -> Tuple[int, int]:
        return (40, len(self.__signals) + 4)

    def __send_signal(self, sig: signal.Signals) -> None:  # pylint: disable=no-member
        os.kill(self.__pid, sig)
        self._emit('close')


class ProcessList(DialogHostMixin, urwid.Filler):
    def __init__(
            self, event_loop: asyncio.AbstractEventLoop, process_manager: core.ProcessManager
    ) -> None:
        self.__text = urwid.Text("")
        super().__init__(self.__text, 'top')

        self.__event_loop = event_loop
        self.__process_manager = process_manager

        self.__processes = {}  # type: Dict[int, ProcessInfo]
        self.__process_list = []  # type: List[ProcessInfo]
        self.__processes_update = True
        self.__processes_sort_column = 'PID'
        self.__processed_sort_dir = 'asc'
        self.__processes_current = 0

        self.__quit = asyncio.Event(loop=self.__event_loop)
        self.__update_task = self.__event_loop.create_task(self.__update_main())

    async def cleanup(self) -> None:
        self.__quit.set()
        await asyncio.wait_for(self.__update_task, None, loop=self.__event_loop)
        self.__update_task.result()

    def selectable(self) -> bool:
        return True

    def keypress(self, size: Tuple[int, ...], key: str) -> Optional[str]:
        if key == ' ':
            self.__update_processes()
            self.__update()
            return None

        if key == 'p':
            self.__processes_update = not self.__processes_update
            self.__update()
            return None

        if key == 'd':
            if self.__processed_sort_dir == 'asc':
                self.__processed_sort_dir = 'desc'
            else:
                self.__processed_sort_dir = 'asc'
            self.__sort_processes()
            self.__update()
            return None

        if key in ('s', 'S'):
            for idx, col in enumerate(process_list_columns):
                if col.title == self.__processes_sort_column:
                    if key == 's':
                        new_idx = (idx + 1) % len(process_list_columns)
                    else:
                        new_idx = (idx - 1) % len(process_list_columns)
                    self.__processes_sort_column = process_list_columns[new_idx].title
                    break
            else:
                self.__processes_sort_column = process_list_columns[0].title
            self.__sort_processes()
            self.__update()
            return None

        if key == 'up':
            if self.__processes_current > 0:
                self.__processes_current -= 1
            self.__update()
            return None

        if key == 'down':
            if self.__processes_current < min(20, len(self.__process_list) - 1):
                self.__processes_current += 1
            self.__update()
            return None

        if key == 'k':
            proc = self.__process_list[self.__processes_current]
            dialog = SignalDialog(proc.pid)
            urwid.connect_signal(dialog, 'close', lambda button: self.hide_dialog())
            self.show_dialog(dialog)
            return None

        return key

    def __update(self) -> None:
        sort_arrow = ARROW_DOWN if self.__processed_sort_dir == 'desc' else ARROW_UP

        rendered = []  # type: List[Union[str, Tuple[str, str]]]

        for idx, col in enumerate(process_list_columns):
            if idx > 0:
                rendered.append(('listheader', ' '))

            out = col.title
            if col.align == '<':
                if col.title == self.__processes_sort_column:
                    out += sort_arrow
                out += ' ' * (col.width - len(out))
            else:
                assert col.align == '>'
                if col.title == self.__processes_sort_column:
                    out = sort_arrow + out
                out = ' ' * (col.width - len(out)) + out

            rendered.append(('listheader', out))
        rendered.append('\n')

        for idx, proc in enumerate(self.__process_list):
            style = 'selected' if idx == self.__processes_current else 'normal'
            out = ''
            for cidx, col in enumerate(process_list_columns):
                if cidx > 0:
                    out += ' '
                value = col.display_func(proc)
                if col.align == '<':
                    value += ' ' * (col.width - len(value))
                else:
                    assert col.align == '>'
                    value = ' ' * (col.width - len(value)) + value
                out += value

            rendered.append((style, out + '\n'))

        self.__text.set_text(rendered)

    async def __update_main(self) -> None:
        while not self.__quit.is_set():
            if self.__processes_update:
                self.__update_processes()

            self.__update()

            wait_tasks = [
                asyncio.sleep(0.5, loop=self.__event_loop),
                self.__quit.wait()
            ]  # type: List[Awaitable]
            _, pending = await asyncio.wait(
                wait_tasks, loop=self.__event_loop, return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()

    def __update_processes(self) -> None:
        stale_pids = set(self.__processes.keys())
        for pid, name in self.__process_manager.processes:
            stale_pids.discard(pid)
            if pid not in self.__processes:
                self.__processes[pid] = ProcessInfo(pid, name)

        for pid in stale_pids:
            del self.__processes[pid]

        for proc in self.__processes.values():
            proc.update()

        self.__sort_processes()

    def __sort_processes(self) -> None:
        processes = None  # type: Iterable[ProcessInfo]
        processes = sorted(
            self.__processes.values(), key=process_key_funcs[self.__processes_sort_column])
        if self.__processed_sort_dir == 'desc':
            processes = reversed(processes)
        processes = itertools.islice(processes, 0, 20)
        self.__process_list = list(processes)


class LogBuffer(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.__records = {}  # type: Dict[int, List[Tuple[int, logging.LogRecord]]]
        self.__next_record_num = 0
        self.__listeners = {}  # type: Dict[str, Callable[[logging.LogRecord], None]]

    @property
    def records(self) -> Iterator[logging.LogRecord]:
        # pylint: disable=protected-access
        heappop = heapq.heappop
        siftup = heapq._siftup  # type: ignore
        _StopIteration = StopIteration

        h = []  # type: List[Any]
        h_append = h.append
        for it in map(iter, self.__records.values()):  # type: ignore
            try:
                h_append([next(it), it])
            except _StopIteration:
                pass
        heapq.heapify(h)

        while 1:
            try:
                while 1:
                    (_, record), it = s = h[0]
                    yield record
                    s[0] = next(it)
                    siftup(h, 0)
            except _StopIteration:
                heappop(h)
            except IndexError:
                return

    def emit(self, record: logging.LogRecord) -> None:
        with self.lock:
            records = self.__records.setdefault(record.levelno, [])
            records.append((self.__next_record_num, record))
            if len(records) > 10000:
                del records[:1]
            self.__next_record_num += 1

            for listener in self.__listeners.values():
                listener(record)

    def add_listener(self, name: str, listener: Callable[[logging.LogRecord], None]) -> None:
        with self.lock:
            assert name not in self.__listeners
            self.__listeners[name] = listener

    def remove_listener(self, name: str) -> None:
        with self.lock:
            self.__listeners.pop(name, None)


class LogViewer(urwid.Widget):
    _sizing = frozenset(['box'])
    _selectable = True
    ignore_focus = True

    def __init__(self, event_loop: asyncio.AbstractEventLoop, log_buffer: LogBuffer) -> None:
        super().__init__()

        self.__mode = 'tail'
        self.__min_loglevel = logging.INFO

        self.__cols = 80
        self.__rows = 20
        self.__lines = []  # type: List[str]
        self.__cursor = 0

        self.__formatter = logging.Formatter(
            '%(levelname)-8s:%(process)5s:%(thread)08x:%(name)s: %(message)s')

        self.__event_loop = event_loop
        self.__log_buffer = log_buffer
        self.__log_buffer.add_listener('viewer', self.__new_record_threadsafe)

    async def cleanup(self) -> None:
        self.__log_buffer.remove_listener('viewer')

    def __new_record_threadsafe(self, record: logging.LogRecord) -> None:
        self.__event_loop.call_soon_threadsafe(self.__new_record, record)

    def __new_record(self, record: logging.LogRecord) -> None:
        if self.__mode != 'tail':
            return

        if not self.__filter(record):
            return

        for line in self.__format(record):
            self.__lines.append(line)

        if len(self.__lines) > 10000:
            del self.__lines[:len(self.__lines) - 10000]

        self._invalidate()

    def __filter(self, record: logging.LogRecord) -> bool:
        if record.levelno < self.__min_loglevel:
            return False

        return True

    def __format(self, record: logging.LogRecord) -> Iterator[str]:
        formatted = self.__formatter.format(record)
        for line in formatted.split('\n'):
            for c in range(0, len(line), self.__cols):
                yield line[c:c+self.__cols]

    def __populate(self) -> None:
        self.__lines = []

        with self.__log_buffer.lock:
            for record in self.__log_buffer.records:
                if not self.__filter(record):
                    continue

                for line in self.__format(record):
                    self.__lines.append(line)

    def render(self, size: Tuple[int, ...], focus: bool = False) -> urwid.Canvas:
        if (self.__cols, self.__rows) != size:
            self.__populate()

        self.__cols, self.__rows = size

        if self.__mode == 'tail':
            lines = self.__lines[-self.__rows:]
        else:
            lines = self.__lines[self.__cursor:self.__cursor + self.__rows]

        lines.extend([''] * (self.__rows - len(lines)))

        e = []
        c = []
        for line in lines:
            line = line[:self.__cols]
            line += ' ' * (self.__cols - len(line))
            text, cs = urwid.apply_target_encoding(line)
            e.append(text)
            c.append(cs)

        return urwid.TextCanvas(e, None, c)

    def keypress(self, size: Tuple[int, ...], key: str) -> Optional[str]:
        _, rows = size

        if key in ('d', 'i', 'w', 'e'):
            self.__min_loglevel = {
                'd': logging.DEBUG,
                'i': logging.INFO,
                'w': logging.WARNING,
                'e': logging.ERROR,
            }[key]
            self.__populate()
            if self.__mode == 'scroll':
                self.__cursor = max(0, len(self.__lines) - rows)
            self._invalidate()
            return None

        if key == 'p':
            if self.__mode == 'tail':
                self.__mode = 'scroll'
                self.__cursor = max(0, len(self.__lines) - rows)
            else:
                self.__mode = 'tail'
                self.__populate()
            self._invalidate()
            return None

        if key in ('up', 'down', 'page up', 'page down', 'home', 'end'):
            if self.__mode != 'scroll':
                self.__mode = 'scroll'
                self.__cursor = max(0, len(self.__lines) - rows)

            if key == 'up':
                self.__cursor = max(self.__cursor - 1, 0)
            elif key == 'down':
                self.__cursor = min(self.__cursor + 1, max(0, len(self.__lines) - self.__rows))
            elif key == 'page up':
                self.__cursor = max(self.__cursor - self.__rows, 0)
            elif key == 'page down':
                self.__cursor = min(
                    self.__cursor + self.__rows, max(0, len(self.__lines) - self.__rows))
            elif key == 'home':
                self.__cursor = 0
            elif key == 'end':
                self.__cursor = max(0, len(self.__lines) - self.__rows)

            self._invalidate()
            return None

        return key


class Screen(urwid.Frame):
    signals = ['quit']

    def __init__(self) -> None:
        super().__init__(None)

        self.__help = HelpPopup()
        urwid.connect_signal(self.__help, 'close', lambda _: self.__close_popup())

        self.__popup = None  # type: Optional[Popup]

    def keypress(self, size: Tuple[int, ...], key: str) -> Optional[str]:
        if key == 'h':
            self.__open_popup(self.__help)
            return None

        if key == 'q':
            self._emit('quit')
            return None

        return super().keypress(size, key)

    def __open_popup(self, popup: Popup) -> None:
        assert self.__popup is None
        self.__popup = popup
        self._invalidate()

    def __close_popup(self) -> None:
        self.__popup = None
        self._invalidate()

    def render(self, size: Tuple[int, ...], focus: bool = False) -> urwid.Canvas:
        canv = super().render(size, focus)

        if self.__popup is not None:
            canv = urwid.CompositeCanvas(canv)
            width, height = size
            pwidth, pheight = self.__popup.size
            canv.set_pop_up(
                self.__popup,
                left=(width - pwidth) // 2,
                top=(height - pheight) // 2,
                overlay_width=pwidth,
                overlay_height=pheight)

        return canv


class DebugConsole(object):
    def __init__(
            self, event_loop: asyncio.AbstractEventLoop, process_manager: core.ProcessManager,
            log_manager: logging.LogManager,
    ) -> None:
        self.__event_loop = event_loop
        self.__process_manager = process_manager
        self.__log_manager = log_manager
        self.__log_buffer = None  # type: LogBuffer
        self.__old_stderr_handler = None  # type: Optional[logging.Handler]

        self.__urwid_loop = None  # type: urwid.MainLoop
        self.__screen = None  # type: urwid.Frame
        self.__title_bar = None  # type: TitleBar
        self.__process_list = None  # type: ProcessList
        self.__log_viewer = None  # type: LogViewer

        self.__quitting = None  # type: bool

    async def setup(self) -> None:
        if not os.isatty(0) or not os.isatty(1):
            raise RuntimeError("Debug console requires a TTY (no shell redirections or piping!).")

        logger.info("Setting up debug console...")

        self.__log_buffer = LogBuffer()
        self.__old_stderr_handler = self.__log_manager.remove_handler('stderr')
        self.__log_manager.add_handler('stderr', self.__log_buffer)

        palette = [
            ('title', 'white', 'dark blue'),
            ('normal', 'light gray', 'black'),
            ('listheader', 'light gray,underline', 'black'),
            ('selected', 'white', 'light gray'),
            ('popup', 'light gray', 'dark blue'),
            ('windowtitle', 'black', 'light gray'),
        ]

        self.__title_bar = TitleBar(self.__event_loop)
        self.__process_list = ProcessList(self.__event_loop, self.__process_manager)
        self.__log_viewer = LogViewer(self.__event_loop, self.__log_buffer)

        body = urwid.Pile([
            ('weight', 1, Window('Processes', self.__process_list)),
            ('weight', 2, Window('Log', self.__log_viewer)),
        ])

        self.__screen = Screen()
        self.__screen.set_body(body)
        self.__screen.set_header(self.__title_bar)

        self.__quitting = False
        urwid.connect_signal(self.__screen, 'quit', lambda _: self.__quit())

        self.__urwid_loop = urwid.MainLoop(
            widget=self.__screen,
            palette=palette,
            pop_ups=True,
            event_loop=urwid.AsyncioEventLoop(loop=self.__event_loop))
        self.__urwid_loop.start()

    async def cleanup(self) -> None:
        if self.__title_bar is not None:
            await self.__title_bar.cleanup()
            self.__title_bar = None

        if self.__log_viewer is not None:
            await self.__log_viewer.cleanup()
            self.__log_viewer = None

        if self.__process_list is not None:
            await self.__process_list.cleanup()
            self.__process_list = None

        if self.__urwid_loop is not None:
            self.__urwid_loop.stop()
            self.__urwid_loop = None

        self.__log_manager.remove_handler('stderr')

        if self.__old_stderr_handler is not None:
            self.__log_manager.add_handler('stderr', self.__old_stderr_handler)
            self.__old_stderr_handler = None

    def __quit(self) -> None:
        if not self.__quitting:
            self.__quitting = True
            self.__event_loop.create_task(self.cleanup())
