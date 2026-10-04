FROM python:3.11-slim

ARG CODEQL_VERSION=2.27.0
ARG SYFT_VERSION=1.52.0
ARG GRYPE_VERSION=0.119.0

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/codeql:${PATH}"

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates curl git tar \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /opt/codeql \
    && curl -fsSL \
        "https://github.com/github/codeql-action/releases/download/codeql-bundle-v${CODEQL_VERSION}/codeql-bundle-linux64.tar.gz" \
        | tar -xz -C /opt/codeql --strip-components=1 \
    && curl -fsSL \
        "https://github.com/anchore/syft/releases/download/v${SYFT_VERSION}/syft_${SYFT_VERSION}_linux_amd64.tar.gz" \
        | tar -xz -C /usr/local/bin syft \
    && curl -fsSL \
        "https://github.com/anchore/grype/releases/download/v${GRYPE_VERSION}/grype_${GRYPE_VERSION}_linux_amd64.tar.gz" \
        | tar -xz -C /usr/local/bin grype \
    && chmod +x /opt/codeql/codeql /usr/local/bin/syft /usr/local/bin/grype

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install --no-cache-dir .

VOLUME ["/app/organizations"]

CMD ["miner", "--help"]
