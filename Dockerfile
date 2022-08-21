FROM python:3.8.13
COPY requirements.txt /
RUN STATIC_DEPS=true pip install -r requirements.txt

COPY zpfwebsite /zpfwebsite
COPY instance /instance
COPY static /static
COPY templates /templates
COPY src /src
COPY app.py /
ENV PYTHONUNBUFFERED 1

ENTRYPOINT ["flask", "run"]
