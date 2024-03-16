FROM python:3.11 as builder
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install -U --no-cache-dir pip \
    && pip install --no-cache-dir -r requirements.txt

FROM danielschenk/python-slim-iot:master

ARG USERNAME=user
ARG USER_UID=1000
ARG USER_GID=$USER_UID

RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN mkdir /instance && chown $USER_UID:$USER_GID /instance
COPY zpfwebsite /zpfwebsite
COPY static /static
COPY templates /templates
COPY src /src
COPY app.py /
ARG VERSION=unknown
RUN echo ${VERSION} > VERSION

USER $USERNAME

ENV HOST=127.0.0.1
ENV PORT=8080
ENTRYPOINT waitress-serve --host=$HOST --port=$PORT --call app:create_app
