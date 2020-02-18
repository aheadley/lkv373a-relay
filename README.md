# LKV373A Stream Relay

lkv373a-relay is a small daemon for transcoding and streaming the output of a
[LKV373A HDMI Extender](https://blog.danman.eu/new-version-of-lenkeng-hdmi-over-ip-extender-lkv373a/)
(transmitter) to Twitch.tv or other streaming services, as
a cheap substitute for a HDMI capture card. The main feature is automatic starting
and stopping of ffmpeg, which (together with an automated power outlet)
allows for simple hands-off streaming with low resource usage.

## Requirements

lkv373a-relay only requires Python 3.6+ with humanize, and ffmpeg. It was originally written
for Python 2.7 and was updated to 3.6 with backwards-compatibility in mind so it
may still work under 2.7, but this is untested.

## Setup

The daemon can be run directly, through systemd, or in Docker.

### Docker

~~~~
$ git clone https://github.com/aheadley/lkv373a-relay.git
$ cd lkv373a-relay
$ docker build . -t lkv373a-relay:latest
$ docker run -p 5004:5004/udp lkv373a-relay:latest 'rtmp://twitch.tv/live/your-stream-key'
~~~~

### SystemD

~~~~
$ git clone https://github.com/aheadley/lkv373a-relay.git
$ cd lkv373a-relay
# cp lkv373a-relay.py /usr/local/bin/lkv373a-relay
# cp lkv373a-relay.service /etc/systemd/system/
# pip3 install -r requirements.txt
## this step may be different for non-RHEL based distros
# cp relay-config.example /etc/sysconfig/lkv373a-relay
## adjust the RTMP URL and --ffmpeg option accordingly
# $EDITOR /etc/sysconfig/lkv373a-relay
# systemctl daemon-reload
# systemctl start lkv373a-relay
~~~~

### Direct

~~~~
$ git clone https://github.com/aheadley/lkv373a-relay.git
$ cd lkv373a-relay
$ virtualenv venv
$ . venv/bin/activate
$ pip install -r requirements.txt
$ ./lkv373a-relay.py 'rtmp://twitch.tv/live/your-stream-key'
~~~~


## Usage

~~~~
usage: lkv373a-relay.py [-h] [-b BITRATE] [-F FFMPEG] [-l LISTEN] [-p PORT]
                        [-r FRAMERATE] [-s SCALE] [-P {twitch,youtube}]
                        [-t TIMEOUT] [-q] [-v]
                        RTMP_URL

positional arguments:
  RTMP_URL              Target RTMP URL for transcoded stream

optional arguments:
  -h, --help            show this help message and exit
  -b BITRATE, --bitrate BITRATE
                        Target bitrate for transcoded stream in kbps (default:
                        5000)
  -F FFMPEG, --ffmpeg FFMPEG
                        Path to ffmpeg executable to use (default: ffmpeg)
  -l LISTEN, --listen LISTEN
                        Address to listen on (default: 0.0.0.0)
  -p PORT, --port PORT  Port to listen on (default: 5004)
  -r FRAMERATE, --framerate FRAMERATE
                        Target framerate for transcoded stream (default: 60)
  -s SCALE, --scale SCALE
                        Target video dimensions for transcoded stream as x:y
                        (default: 1920:1080)
  -P {twitch,youtube}, --profile {twitch,youtube}
                        Target transcoding profile (default: twitch)
  -t TIMEOUT, --timeout TIMEOUT
                        Timeout to kill transcode process after last packet
                        received (default: 10.0)
  -q, --quiet
  -v, --verbose
~~~~

**NOTE:** The docker image already includes ffmpeg and the `-F` option.
