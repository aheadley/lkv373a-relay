#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
import logging
import shlex
import socket
import subprocess
import sys
import time
import traceback
try:
    import socketserver
except ImportError:
    # py2k backwards compat
    import SocketServer as socketserver

import humanize

try:
    timer_now = time.monotonic
except AttributeError:
    # py2k backwards compat
    timer_now = time.time

log = logging.getLogger('lkv373a-relay')

COMMAND_BASE_ARGS = [
    '-hide_banner', '-loglevel', 'panic', '-nostats', '-y',
    '-strict', '-2', '-threads', '0',
    '-i', 'pipe:0',
]
COMMAND_PROFILE_TEMPLATES = {
    'twitch': [
        '-vf', 'scale={scale},fps=fps={framerate}',
        '-vcodec', 'libx264', '-g', '{framerate_dbl}', '-keyint_min', '{framerate}',
        '-bufsize', '10m', '-preset', 'veryfast',
        '-b:v', '{bitrate}k', '-maxrate', '{bitrate}k', '-pix_fmt', 'yuv420p',
        '-codec:a', 'aac', '-b:a', '128k', '-ar', '44100', '-ac', '2',
        '-f', 'flv',
    ],
}
# TODO: find actual settings for youtube
COMMAND_PROFILE_TEMPLATES['youtube'] = COMMAND_PROFILE_TEMPLATES['twitch']

class Timer:
    def __init__(self):
        self._start = self._stop = 0.0
        
    def __enter__(self):
        self.start()
        
        return self
        
    def __exit__(self, *args):
        self.stop()
        
        return self
    
    def start(self):
        self._start = timer_now()
        
    def stop(self):
        self._stop = timer_now()
        try:
            ctx_line = traceback.extract_stack()[-3]
            log.debug('%s:%d -> [%s] time elapsed: %fs', ctx_line[0], ctx_line[1], ctx_line[3], self.elapsed)
        except IndexError: pass                                                                    
        return self.elapsed

    @property
    def elapsed(self):
        return abs(self._stop - self._start)

class VideoStreamHandler(socketserver.BaseRequestHandler):
    def setup(self):
        self.server.process_start(self.client_address)

    def handle(self):
        data = self.request[0]
        self.server.last_packet_timestamp = timer_now()
        self.server.process_handle.stdin.write(data)
        self.server._traffic_handled += len(data)

class VideoStreamServer(socketserver.UDPServer):
    def __init__(self, server_address, RequestHandlerClass, bind_and_activate=True, cmd=['/bin/false']):
        super(VideoStreamServer, self).__init__(server_address, RequestHandlerClass, bind_and_activate)

        self.last_packet_timestamp = timer_now()
        self._process_timer = None
        self._traffic_handled = 0
        self._process_cmd = cmd
        self.process_handle = None
    
    def _addr_to_str(self, socket_addr):
        if socket_addr is None: # no arg passed to process_start()
            return '<unknown>'
        if isinstance(socket_addr, str): # unix socket
            return socket_addr
        if len(socket_addr) == 2: # IPv4
            return '{:s}:{:d}'.format(socket_addr[0], socket_addr[1])
        if len(socket_addr) == 4: # IPv6
            return '[{:s}]:{:d}'.format(socket_addr[0], socket_addr[1])
        return repr(socket_addr) # ???
    
    def handle_error(self, request, client_address):
        log.error('Exception happened during processing of request from: %s', self._addr_to_str(client_address))
        _, err, _ = sys.exc_info()
        log.exception(err)

    def process_start(self, start_for=None):
        if not self.process_running:
            log.info('Proc not running, starting for: %s', self._addr_to_str(start_for))
            self._process_timer = Timer()
            try:
                self.process_handle = subprocess.Popen(self._process_cmd, stdin=subprocess.PIPE)
            except (IOError, OSError) as err:
                log.error('Unable to start process, shutting down')
                log.exception(err)
                self.shutdown()
            else:
                self._process_timer.start()
                self._traffic_handled = 0

    def process_stop(self):
        if self.process_running:
            log.info('Stopping proc: pid=%d', self.process_handle.pid)
            with Timer() as stop_timer:
                self.process_handle.kill()
                self.process_handle.wait()
                self._process_timer.stop()

            log.debug('Time taken to stop proc: %fs', stop_timer.elapsed)
            log.info('Proc run stats: runtime=%.1fs (%s) data=%s rate=%s/s',
                self._process_timer.elapsed,
                humanize.naturaldelta(datetime.timedelta(seconds=self._process_timer.elapsed)),
                humanize.naturalsize(self._traffic_handled, binary=True),
                humanize.naturalsize(self._traffic_handled/self._process_timer.elapsed, binary=True))
            self.process_handle = None
            self._process_timer = None
            self._traffic_handled = 0

    def process_restart(self):
        self.process_stop()
        self.process_start()

    @property
    def process_running(self):
        if self.process_handle is not None:
            poll_result = self.process_handle.poll()
            if poll_result is None:
                return True
            log.warning('Proc poll() returned: %r', poll_result)
        return False
    
    def process_timeout_watchdog(self, timeout=10.0):
        while True:
            if timer_now() - self.last_packet_timestamp > timeout:
                if self.process_running:
                    log.info('No traffic received for %d seconds, stopping process', timeout)
                    self.process_stop()
            # sleep for at least 1 second, but aim for (timeout/2)-1
            time.sleep(max(1.0, timeout / 2.0 - 1.0))
    
def build_command(args):
    if not args.stream_endpoint.lower().startswith('rtmp'):
        log.warning('Streaming endpoint does not look like a RTMP URL')
    cmd_args = [args.ffmpeg] + COMMAND_BASE_ARGS + \
        COMMAND_PROFILE_TEMPLATES[args.profile][:] + [args.stream_endpoint]
    cmd = shlex.split(' '.join(shlex.quote(a) for a in cmd_args).format(
        framerate_dbl=args.framerate * 2,
        framerate=args.framerate,
        bitrate=args.bitrate,
        scale=args.scale,
    ))
    log.debug('Built command: %s', ' '.join(cmd))

    return cmd

if __name__ == '__main__':
    import argparse
    import threading
    
    class IncrementAction(argparse.Action):
        def __init__(self, option_strings, dest, nargs=0, default=0, **kwargs):
            if nargs != 0:
                raise ValueError('nargs not allowed')
            super(IncrementAction, self).__init__(option_strings, dest, default=default, nargs=0, **kwargs)
        
        def __call__(self, parser, namespace, values, option_string=None):
            setattr(namespace, self.dest, getattr(namespace, self.dest) + 1)
    class DecrementAction(IncrementAction):
        def __call__(self, parser, namespace, values, option_string=None):
            setattr(namespace, self.dest, getattr(namespace, self.dest) - 1)

    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter, allow_abbrev=False)
    parser.add_argument('-b', '--bitrate', default=5000, type=int,
        help='Target bitrate for transcoded stream in kbps')
    parser.add_argument('-F', '--ffmpeg', default='ffmpeg',
        help='Path to ffmpeg executable to use')
    parser.add_argument('-l', '--listen', default='0.0.0.0',
        help='Address to listen on')
    parser.add_argument('-p', '--port', default=5004, type=int,
        help='Port to listen on')
    parser.add_argument('-r', '--framerate', default=60, type=int,
        help='Target framerate for transcoded stream')
    parser.add_argument('-s', '--scale', default='1920:1080',
        help='Target video dimensions for transcoded stream as x:y')
    parser.add_argument('-P', '--profile', default='twitch',
        choices=list(COMMAND_PROFILE_TEMPLATES.keys()),
        help='Target transcoding profile')
    parser.add_argument('-t', '--timeout', default=10.0, type=float,
        help='Timeout to kill transcode process after last packet received')
    parser.add_argument('-q', '--quiet', action=IncrementAction, default=2, dest='loglevel')
    parser.add_argument('-v', '--verbose', action=DecrementAction, default=2, dest='loglevel')
    parser.add_argument('stream_endpoint', metavar='RTMP_URL', default='/dev/null',
        help='Target RTMP URL for transcoded stream')

    args = parser.parse_args()
    
    loglevel = 10 * min(max(args.loglevel, 1), 5)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(fmt='%(levelname)s - %(message)s'))
    log.addHandler(handler)
    log.setLevel(loglevel)

    server = VideoStreamServer((args.listen, args.port), VideoStreamHandler, cmd=build_command(args))
    watchdog_thread = threading.Thread(target=server.process_timeout_watchdog, args=(args.timeout,))
    watchdog_thread.daemon = True

    watchdog_thread.start()
    server.serve_forever()
