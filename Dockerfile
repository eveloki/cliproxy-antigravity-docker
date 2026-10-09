# syntax=docker/dockerfile:1
# Personal stable distribution. Fixed official CLI; no account is baked in.
FROM debian:bookworm-slim AS agy-builder
ARG AGY_VERSION=1.2.12
ARG AGY_SHA256=26c7c4c661d6c9beda734fcf305031056a6ea46e697c4533e8151179724e2950
ARG TARGETARCH
RUN test "$TARGETARCH" = amd64 && \
    apt-get update && apt-get install -y --no-install-recommends ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*
RUN curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' \
      --connect-timeout 20 --max-time 300 --retry 3 \
      "https://github.com/google-antigravity/antigravity-cli/releases/download/${AGY_VERSION}/agy_cli_linux_x64.tar.gz" \
      --output /tmp/agy.tar.gz && \
    printf '%s  /tmp/agy.tar.gz\n' "$AGY_SHA256" | sha256sum --check --status && \
    mkdir -p /out/agy && tar -xzf /tmp/agy.tar.gz --no-same-owner -C /out/agy antigravity && \
    mv /out/agy/antigravity /out/agy/agy && chmod 755 /out/agy/agy && \
    printf '%s\n' "$AGY_VERSION" > /out/agy/VERSION && \
    printf 'AGY_VERSION=%s\nAGY_ARCHIVE_SHA256=%s\nAGY_SOURCE=https://github.com/google-antigravity/antigravity-cli\n' \
      "$AGY_VERSION" "$AGY_SHA256" > /out/agy/provenance.txt && rm /tmp/agy.tar.gz
FROM golang:1.26-bookworm AS builder
ARG CPA_COMMIT=67465884ca179a8f9098328d03a361b50003fdd7
ARG PLUGIN_COMMIT=89d4a3ded47a375a446eac8739a03f6cbda00755
ARG CPA_VERSION=v8.0.22
ARG PLUGIN_VERSION=v0.1.3
ENV CGO_ENABLED=1 GOTOOLCHAIN=local
RUN apt-get update && apt-get install -y --no-install-recommends build-essential git python3 ca-certificates && rm -rf /var/lib/apt/lists/*
COPY scripts/fetch-source.sh /usr/local/bin/fetch-source
RUN chmod 755 /usr/local/bin/fetch-source && \
    fetch-source https://github.com/router-for-me/CLIProxyAPI.git "$CPA_COMMIT" /src/cpa && \
    fetch-source https://github.com/adeebahmad01/cliproxy-antigravity.git "$PLUGIN_COMMIT" /src/plugin
WORKDIR /src/cpa
RUN go mod download && go mod verify && \
    go build -trimpath -buildvcs=false -ldflags="-s -w -X main.Version=${CPA_VERSION} -X main.Commit=${CPA_COMMIT} -X main.BuildDate=$(date -u +%Y-%m-%dT%H:%M:%SZ)" -o /out/CLIProxyAPI ./cmd/server/
WORKDIR /src/plugin
COPY compat/ /compat/
RUN git apply --check /compat/plugin-model-router.patch && \
    git apply /compat/plugin-model-router.patch && \
    cp /compat/distribution_router*.go . && \
    gofmt -w distribution_router*.go plugin.go && \
    go test ./... && \
    go build -trimpath -buildmode=c-shared -ldflags="-s -w" -o /out/cliproxy-antigravity.so . && \
    python3 scripts/abi_smoke.py /out/cliproxy-antigravity.so
RUN mkdir -p /out/licenses && \
    cp /src/cpa/LICENSE /out/licenses/CLIProxyAPI.LICENSE && \
    cp /src/plugin/LICENSE /out/licenses/cliproxy-antigravity.LICENSE && \
    cp /src/plugin/THIRD_PARTY_NOTICES.md /out/licenses/plugin-THIRD_PARTY_NOTICES.md && \
    printf 'CPA_VERSION=%s\nCPA_COMMIT=%s\nPLUGIN_VERSION=%s\nPLUGIN_COMMIT=%s\n' "$CPA_VERSION" "$CPA_COMMIT" "$PLUGIN_VERSION" "$PLUGIN_COMMIT" > /out/upstream-versions.txt
RUN printf 'PLUGIN_COMPAT=cpa8-route1\n' >> /out/upstream-versions.txt && \
    cd /compat && sha256sum plugin-model-router.patch distribution_router.go >> /out/upstream-versions.txt

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash ca-certificates curl tini python3 python3-yaml util-linux tzdata libstdc++6 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 cliproxy \
    && useradd --uid 10001 --gid 10001 --create-home --shell /bin/bash cliproxy \
    && mkdir -p /CLIProxyAPI/plugins /CLIProxyAPI/logs /CLIProxyAPI/data/agy-workspace /root/.cli-proxy-api /config /opt/cliproxy/bundled-plugins /home/cliproxy/plugins /home/cliproxy/.local/bin /home/cliproxy/.gemini /home/cliproxy/.cli-proxy-api /home/cliproxy/workspace \
    && chown -R 10001:10001 /config /home/cliproxy \
    && chmod 700 /config /home/cliproxy
COPY --from=builder /out/CLIProxyAPI /opt/cliproxy/CLIProxyAPI
COPY --from=builder /out/cliproxy-antigravity.so /opt/cliproxy/bundled-plugins/cliproxy-antigravity.so
COPY --from=builder /out/licenses/ /opt/cliproxy/licenses/
COPY --from=builder /out/upstream-versions.txt /opt/cliproxy/upstream-versions.txt
COPY --from=agy-builder /out/agy/ /opt/agy/
COPY scripts/ /opt/cliproxy/scripts/
COPY config.example.yaml LICENSE THIRD_PARTY_NOTICES.md STATUS /opt/cliproxy/
RUN chmod 755 /opt/cliproxy/scripts/*.sh && \
    ln -s /opt/cliproxy/scripts/agy.sh /usr/local/bin/agy && \
    ln -s /opt/cliproxy/CLIProxyAPI /CLIProxyAPI/CLIProxyAPI && \
    ln -s /home/cliproxy/plugins /opt/cliproxy/plugins && \
    ln -snf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime && \
    printf '%s\n' Asia/Shanghai > /etc/timezone && \
    cp /opt/cliproxy/config.example.yaml /CLIProxyAPI/config.example.yaml && \
    cat /opt/agy/provenance.txt >> /opt/cliproxy/upstream-versions.txt
ENV HOME=/root \
    GEMINI_FORCE_FILE_STORAGE=true \
    AGY_CLI_DISABLE_AUTO_UPDATE=true \
    TZ=Asia/Shanghai
LABEL org.opencontainers.image.title="CLIProxyAPI Antigravity Docker" \
      org.opencontainers.image.description="Stable personal distribution with a pinned official agy binary." \
      io.cliproxy.distribution.status="STABLE" \
      io.cliproxy.distribution.channel="stable"
USER root
WORKDIR /CLIProxyAPI
EXPOSE 8317 8085 1455 54545 51121 11451
# Liveness only. Does not call Google or certify authentication.
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD ["python3", "/opt/cliproxy/scripts/healthcheck.py"]
ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/opt/cliproxy/scripts/entrypoint.sh"]
CMD ["./CLIProxyAPI"]
