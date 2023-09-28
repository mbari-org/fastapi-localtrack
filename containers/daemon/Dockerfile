# ================================================================
#  Docker image for fastapi-localtrack-daemon
#  ================================================================
FROM ubuntu:20.04
LABEL vendor="MBARI"
LABEL maintainer="Danelle Cline dcline@mbari.org"
LABEL license="GPL"

ARG IMAGE_URI=mbari/fastapi-localtrack-daemon

ENV DEBIAN_FRONTEND=noninteractive
RUN apt update -y && apt install -y software-properties-common && \
    add-apt-repository -y ppa:deadsnakes/ppa &&  \
    apt-get install -y git \
	&& apt-get install -y build-essential \
	&& apt-get install -y python3.10 \
    && apt-get install -y python3-pip \
	&& apt-get install -y python3.10-dev \
	&& apt-get install -y python3.10-distutils \
	&& apt-get install -y libgl1-mesa-glx \
	&& apt-get install -y libglib2.0-0 \
	&& apt-get install -y libncurses6 \
    && apt-get install -y curl \
    && curl -sS https://bootstrap.pypa.io/get-pip.py | python3.10 \
    && python3.10 -m pip install --upgrade pip==23.2.1 \
    && apt-get clean

ENV WORKERS_PER_CORE=4
ENV MAX_WORKERS=24
ENV LOG_LEVEL="warning"
ENV TIMEOUT="200"

## force stdin, stdout and stderr to be unbuffered to log
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONIOENCODING=UTF-8 LANG=C.UTF-8 LC_ALL=C.UTF-8

## setup virtualenv
RUN pip install virtualenv
RUN virtualenv /env -p python3
ENV VIRTUAL_ENV /env
ENV PATH /env/bin:$PATH

## install requirements
ENV PYTHONPATH=/src
WORKDIR /src/app
COPY ./src/requirements.txt /src/requirements.txt
COPY ./src /src
RUN pip install --no-cache-dir --upgrade -r /src/requirements.txt

# run the daemon
ENTRYPOINT ["python", "-m", "daemon"]