FROM danielschenk/python-slim-iot:master
COPY requirements.txt /
RUN STATIC_DEPS=true pip install -r requirements.txt --no-cache-dir

COPY zpfwebsite /zpfwebsite
COPY instance /instance
COPY static /static
COPY templates /templates
COPY src /src
COPY app.py /
ARG VERSION=unknown
RUN echo ${VERSION} > VERSION
ENV PYTHONUNBUFFERED 1

ENTRYPOINT ["flask", "run"]
