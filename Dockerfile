FROM python:3.8-alpine
COPY requirements.txt /
# musl-dev and gcc required to build backports.zoneinfo with pip
RUN apk add -u gcc musl-dev && \
    pip install -r requirements.txt && \
    apk del gcc musl-dev

COPY zpfwebsite /zpfwebsite
COPY instance /instance
COPY app.py /
ENV PYTHONUNBUFFERED 1

ENTRYPOINT ["flask", "run"]
