FROM python:3.8-slim

COPY requirements.txt /
RUN pip install -r requirements.txt

COPY zpfwebsite /zpfwebsite
COPY instance /instance
COPY app.py /
ENV PYTHONUNBUFFERED 1

ENTRYPOINT ["flask", "run"]
