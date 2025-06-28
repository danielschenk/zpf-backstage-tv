FROM python:3.13

COPY requirements.txt .
RUN pip install -U --no-cache-dir pip \
    && pip install --no-cache-dir -r requirements.txt

ARG USERNAME=user
ARG USER_UID=1000
ARG USER_GID=$USER_UID

RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME

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
