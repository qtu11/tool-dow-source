# webgrabber/Dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y build-essential

COPY . /app
WORKDIR /app

RUN pip install -r requirements.txt
RUN python setup.py install

CMD ["webgrabber", "--help"]