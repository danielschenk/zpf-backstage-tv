FROM python:3.8-alpine
COPY requirements.txt /

# build dependencies for certain pip packages
ARG PIP_BUILD_DEPS="gcc musl-dev"
RUN apk add -u \ 
    ${PIP_BUILD_DEPS} \
    py3-lxml=4.8.0-r0 \
    && \
    pip install -r requirements.txt && \
    apk del ${PIP_BUILD_DEPS}

COPY zpfwebsite /zpfwebsite
COPY instance /instance
COPY app.py /
ENV PYTHONUNBUFFERED 1

ENTRYPOINT ["flask", "run"]
