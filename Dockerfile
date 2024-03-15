FROM python:3.11 as builder
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install -U --no-cache-dir pip \
    && pip install --no-cache-dir -r requirements.txt

FROM danielschenk/python-slim-iot:master

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY zpfwebsite /zpfwebsite
COPY instance /instance
COPY static /static
COPY templates /templates
COPY src /src
COPY app.py /
ARG VERSION=unknown
RUN echo ${VERSION} > VERSION

ENTRYPOINT ["flask", "run"]
