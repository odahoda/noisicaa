#!/usr/bin/python3

import enum
import logging
import os
import os.path
import select
import socket
import tempfile
import threading
import time
import uuid


class ConnState(enum.Enum):
    READ_MESSAGE = 1
    READ_PAYLOAD = 2

class ServerConnection(object):
    def __init__(self, conn):
        self.conn = conn
        self.inbuf = bytearray()
        self.outbuf = bytearray()
        self.state = ConnState.READ_MESSAGE
        self.command = None
        self.payload_length = None

class Server(object):
    def __init__(self, name, socket_dir=None):
        self.logger = logging.getLogger(__name__ + '.' + name)

        if socket_dir is None:
            socket_dir = tempfile.gettempdir()

        self.name = name
        self.address = os.path.join(
            socket_dir, '%s.%s.sock' % (self.name, uuid.uuid4().hex))

        self._socket = None
        self._server_thread = None
        self._connections = {}

        self._command_handlers = {}

    def add_command_handler(self, cmd, handler):
        assert cmd not in self._command_handlers
        self._command_handlers[cmd] = handler

    def setup(self):
        self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._socket.bind(self.address)
        self._socket.listen()

        self._poller = select.epoll()
        self._poller.register(self._socket.fileno(), select.EPOLLIN)
        self._closed = False

    def start(self):
        self._server_thread = threading.Thread(target=self.mainloop)
        self._server_thread.start()

    def cleanup(self):
        if self._server_thread is not None:
            self.send_close()
            self._server_thread.join()
            self._server_thread = None

        if self._socket is not None:
            self._socket.close()
            self._socket = None

    def __enter__(self):
        self.setup()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
        return False

    def send_close(self):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(self.address)
        sock.sendall(b'CLOSE\n')
        sock.close()

    def wait_for_pending_connections(self):
        while len(self._connections) > 0:
            time.sleep(0.01)

    def handle_connections(self):
        for fd, event in self._poller.poll(0.1):
            if fd == self._socket.fileno():
                conn, addr = self._socket.accept()
                self.logger.info(
                    "Accepted new connection on FD %d", conn.fileno())
                conn.setblocking(0)
                self._poller.register(
                    conn.fileno(), select.EPOLLIN | select.EPOLLHUP)
                self._connections[conn.fileno()] = ServerConnection(conn)

            elif fd in self._connections:
                conn = self._connections[fd]
                if event & select.EPOLLIN:
                    data = os.read(fd, 1024)
                    conn.inbuf.extend(data)

                    while conn.inbuf:
                        if conn.state == ConnState.READ_MESSAGE:
                            try:
                                eol = conn.inbuf.index(b'\n')
                            except ValueError:
                                break

                            header = bytes(conn.inbuf[:eol])
                            conn.inbuf = conn.inbuf[eol+1:]
                            if header == b'PING':
                                self.logger.info("PING received")
                                conn.outbuf.extend(b'PONG')
                                self._poller.modify(
                                    fd, select.EPOLLIN | select.EPOLLOUT | select.EPOLLHUP)
                            elif header == b'CLOSE':
                                self.logger.info("CLOSE received")
                                conn.conn.close()
                                self._closed = True

                            elif header.startswith(b'CALL '):
                                command, length = header[5:].split(b' ')
                                conn.command = command.decode('ascii')
                                conn.payload_length = int(length)
                                self.logger.info("CALL %s received (%d bytes payload)", conn.command, conn.payload_length)
                                if conn.payload_length > 0:
                                    conn.state = ConnState.READ_PAYLOAD
                                else:
                                    response = self.handle_command(conn.command, b'')
                                    response = response or b''
                                    conn.outbuf.extend(b'ACK %d\n' % len(response))
                                    conn.outbuf.extend(response)
                                    self._poller.modify(
                                        fd, select.EPOLLIN | select.EPOLLOUT | select.EPOLLHUP)

                            else:
                                self.logger.error("Received unknown message '%s'", header)
                        elif conn.state == ConnState.READ_PAYLOAD:
                            if len(conn.inbuf) < conn.payload_length:
                                break
                            payload = bytes(conn.inbuf[:conn.payload_length])
                            del conn.inbuf[:conn.payload_length]
                            self.logger.info("payload: %s", payload)
                            response = self.handle_command(conn.command, payload)
                            response = response or b''
                            conn.outbuf.extend(b'ACK %d\n' % len(response))
                            conn.outbuf.extend(response)
                            self._poller.modify(
                                fd, select.EPOLLIN | select.EPOLLOUT | select.EPOLLHUP)
                            conn.state = ConnState.READ_MESSAGE
                            conn.command = None
                            conn.payload_length = None

                if event & select.EPOLLOUT:
                    assert conn.outbuf
                    sent = conn.conn.send(conn.outbuf)
                    conn.outbuf = conn.outbuf[sent:]
                    if not conn.outbuf:
                        self._poller.modify(
                            fd, select.EPOLLIN | select.EPOLLHUP)

                if event & select.EPOLLHUP:
                    self.logger.info("Connection %d closed.", fd)
                    self._poller.unregister(fd)
                    del self._connections[fd]
                    conn.conn.close()

            else:
                self.logger.error(
                    "Unexpected poll event %d for FD %d", event, fd)

    def mainloop(self):
        while not self._closed:
            self.handle_connections()

    def handle_command(self, command, payload):
        try:
            handler = self._command_handlers[command]
        except KeyError:
            self.logger.error(
                "Unexpected command %s received.", command)
            return None
        else:
            return handler(payload)


class Stub(object):
    def __init__(self, server_address):
        self.server_address = server_address
        self._socket = None

    def connect(self):
        assert self._socket is None
        self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._socket.connect(self.server_address)

    def close(self):
        assert self._socket is not None
        self._socket.close()
        self._socket = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def call(self, cmd, payload=b''):
        if not isinstance(cmd, bytes):
            cmd = cmd.encode('ascii')
        self._socket.sendall(b'CALL %s %d\n' % (cmd, len(payload)))
        self._socket.sendall(payload)

        buf = bytearray()
        state = 0
        length = None
        response = None
        while state != 2:
            data = self._socket.recv(1024)
            if not data:
                break
            buf.extend(data)

            while buf:
                if state == 0:
                    eol = buf.find(b'\n')
                    if eol == -1:
                        break
                    ack, length = buf[:eol].split(b' ')
                    length = int(length)
                    del buf[:eol+1]
                    assert ack == b'ACK'
                    if length > 0:
                        state = 1
                    else:
                        state = 2
                elif state == 1:
                    if len(buf) < length:
                        break
                    response = bytes(buf[:length])
                    del buf[:length]
                    state = 2
        return response

    def ping(self):
        self._socket.sendall(b'PING\n')
        response = self._socket.recv(1024)
        assert response == b'PONG'
