FROM python:3.8-slim
COPY requirements.txt /

# build dependencies for certain pip packages,
# for which a wheel doesn't always exist
ARG PIP_BUILD_DEPS="gcc libxml2-dev libxslt-dev"
RUN apt-get update &&  \
    apt-get install -y --no-install-recommends \
    ${PIP_BUILD_DEPS} \
    && \
    pip install -r requirements.txt && \
    apt-get remove -y \
    ${PIP_BUILD_DEPS} \
    && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

COPY zpfwebsite /zpfwebsite
COPY instance /instance
COPY app.py /
ENV PYTHONUNBUFFERED 1

ENTRYPOINT ["flask", "run"]
