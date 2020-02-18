FROM alpine:latest

COPY . /app
WORKDIR /app

# install latest stable static ffmpeg, ignore the bad exit code from tar
RUN wget -qO- 'https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz' \
	| tar -xJf - --strip-components=1 'ffmpeg-*/ffmpeg' \
	|| true \
	; mv ffmpeg /usr/local/bin/ffmpeg

# install python3 and requirements
RUN apk add python3 \
	&& python3 -m pip install -r /app/requirements.txt

# not listening on a privileged port so no need to run as root
EXPOSE 5004/udp
USER nobody:nobody

# let the user specify their own options, but force using the installed ffmpeg
# for ease of use
ENTRYPOINT ["python3", "/app/lkv373a-relay.py", "-F", "/usr/local/bin/ffmpeg"]
