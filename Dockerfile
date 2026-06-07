# syntax=docker/dockerfile:1

# === BUILD STAGE ===

FROM dhi.io/python:3.14-dev AS builder

## Python Packages

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# === RUNTIME STAGE ===

FROM dhi.io/python:3.14

LABEL org.opencontainers.image.title="Defender of the Faith"
LABEL org.opencontainers.image.description="Trusted Discord server administrative bot."
LABEL org.opencontainers.image.authors="self@matthewrease.net"

# Package Files

COPY --from=builder /opt/python /opt/python

# App Files

WORKDIR /app
USER nonroot
COPY . .

# Runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENTRYPOINT ["python"]
CMD ["bot.py"]

ARG VERSION
ENV VERSION=${VERSION}
