# syntax=docker/dockerfile:1

FROM python:3

LABEL org.opencontainers.image.title="Defender of the Faith"
LABEL org.opencontainers.image.description="Trusted Discord server administrative bot."
LABEL org.opencontainers.image.authors="self@matthewrease.net"

# Files

WORKDIR /app

## Python Packages

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

## Main Files

COPY . .

# Runtime

ENV PYTHONDONTWRITEBYTECODE=1

CMD ["python3", "bot.py"]

ARG VERSION
ENV VERSION=${VERSION}
