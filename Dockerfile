# syntax=docker/dockerfile:1
# Experimental distribution. No Google executable or account is baked in.
FROM golang:1.26-bookworm AS builder
ARG CPA_COMMIT=acdace936fa7df2905500c7f5e0a97d683138dea
ARG PLUGIN_COMMIT=89d4a3ded47a375a446eac8739a03f6cbda00755
ARG CPA_VERSION=v8.0.3
ARG PLUGIN_VERSION=v0.1.3
ENV CGO_ENABLED=1 GOTOOLCHAIN=local
RUN apt-get update && apt-get install -y --no-install-recommends build-essential git python3 ca-certificates && rm -rf /var/lib/apt/lists/*
COPY scripts/fetch-source.sh /usr/local/bin/fetch-source
RUN chmod 755 /usr/local/bin/fetch-source && \
    fetch-source https://github.com/router-for-me/CLIProxyAPI.git "$CPA_COMMIT" /src/cpa && \
    fetch-source https://github.com/adeebahmad01/cliproxy-antigravity.git "$PLUGIN_COMMIT" /src/plugin
WORKDIR /src/cpa
RUN go mod download && go mod verify && \
    go build -trimpath -buildvcs=false -ldflags="-s -w -X main.Version=${CPA_VERSION} -X main.Commit=${CPA_COMMIT}" -o /out/CLIProxyAPI ./cmd/server/
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
    && mkdir -p /config /opt/cliproxy/plugins /home/cliproxy/.local/bin /home/cliproxy/.gemini /home/cliproxy/.cli-proxy-api /home/cliproxy/workspace \
    && chown -R 10001:10001 /config /home/cliproxy \
    && chmod 700 /config /home/cliproxy
COPY --from=builder /out/CLIProxyAPI /opt/cliproxy/CLIProxyAPI
COPY --from=builder /out/cliproxy-antigravity.so /opt/cliproxy/plugins/cliproxy-antigravity.so
COPY --from=builder /out/licenses/ /opt/cliproxy/licenses/
COPY --from=builder /out/upstream-versions.txt /opt/cliproxy/upstream-versions.txt
COPY scripts/ /opt/cliproxy/scripts/
COPY config.example.yaml LICENSE THIRD_PARTY_NOTICES.md STATUS /opt/cliproxy/
RUN chmod 755 /opt/cliproxy/scripts/*.sh && \
    ln -s /opt/cliproxy/scripts/agy.sh /usr/local/bin/agy
ENV HOME=/home/cliproxy \
    GEMINI_FORCE_FILE_STORAGE=true \
    AGY_CLI_DISABLE_AUTO_UPDATE=true \
    AGY_AUTO_INSTALL=true \
    TZ=Asia/Shanghai
LABEL org.opencontainers.image.title="CLIProxyAPI Antigravity Docker (experimental)" \
      org.opencontainers.image.description="NOT READY — PENDING TESTS. Community thin distribution; installs agy at runtime." \
      io.cliproxy.distribution.status="NOT_READY_PENDING_TESTS"
USER 10001:10001
WORKDIR /home/cliproxy/workspace
EXPOSE 8317
# Liveness only. Does not call Google or certify authentication.
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD ["python3", "/opt/cliproxy/scripts/healthcheck.py"]
ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/opt/cliproxy/scripts/entrypoint.sh"]
CMD ["serve"]
