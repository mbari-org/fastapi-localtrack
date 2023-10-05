# ================================================================
#  Docker image for fastapi-localtrack
#  ================================================================
FROM ubuntu:20.04
LABEL vendor="MBARI"
LABEL maintainer="Danelle Cline dcline@mbari.org"
LABEL license="Apache License 2.0"

ARG IMAGE_URI=mbari/fastapi-localtrack

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


ARG APP_DIR=/app
WORKDIR $APP_DIR

## setup virtualenv
RUN pip install virtualenv
RUN virtualenv $APP_DIR/env -p python3
ENV VIRTUAL_ENV $APP_DIR/env
ENV PATH $APP_DIR/env/bin:$PATH

# install requirements and copy source
ENV PYTHONPATH=$APP_DIR/src
WORKDIR $APP_DIR/src/app
COPY ./src/requirements.txt $APP_DIR/src/requirements.txt
COPY ./src/app $APP_DIR/src/app
COPY config.yml  $APP_DIR/config.yml
RUN pip install --no-cache-dir --upgrade -r $APP_DIR/src/requirements.txt


# run the FastAPI server
EXPOSE 80
ENTRYPOINT ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
