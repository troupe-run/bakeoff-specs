# runner/images/base/Dockerfile — the one environment every arm shares (design §6, §11; spike B Q1).
# Every FROM is by digest (review S-5); the values come from pins.toml via `runner images build`.
ARG DEBIAN_IMAGE
ARG NODE_IMAGE
ARG UV_IMAGE
FROM ${NODE_IMAGE} AS node
FROM ${UV_IMAGE} AS uv

FROM ${DEBIAN_IMAGE} AS os
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl git procps jq \
 && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --uid 1000 --shell /bin/bash actor

FROM os AS claude
ARG CLAUDE_VERSION
ARG CLAUDE_SHA256
USER actor
RUN curl -fsSL https://claude.ai/install.sh | bash -s ${CLAUDE_VERSION} \
 && cp -L /home/actor/.local/share/claude/versions/${CLAUDE_VERSION} /home/actor/claude-bin \
 && if [ -n "${CLAUDE_SHA256}" ]; then echo "${CLAUDE_SHA256}  /home/actor/claude-bin" | sha256sum -c -; fi

FROM os AS gh
ARG GH_VERSION
ARG TARGETARCH
RUN curl -fsSLo /tmp/gh.tgz https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_linux_${TARGETARCH}.tar.gz \
 && curl -fsSLo /tmp/sums https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_checksums.txt \
 && (cd /tmp && grep " gh_${GH_VERSION}_linux_${TARGETARCH}.tar.gz$" sums | awk '{print $1"  gh.tgz"}' | sha256sum -c -) \
 && tar -xzf /tmp/gh.tgz -C /tmp && cp /tmp/gh_${GH_VERSION}_linux_${TARGETARCH}/bin/gh /gh

FROM os
COPY --from=claude --chmod=0755 /home/actor/claude-bin /usr/local/bin/claude
COPY --from=uv /uv /uvx /usr/local/bin/
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx
COPY --from=gh --chmod=0755 /gh /usr/local/bin/gh
ENV UV_PYTHON_INSTALL_DIR=/opt/python UV_PYTHON_PREFERENCE=only-managed
RUN uv python install 3.12 && chmod -R a+rX /opt/python \
 && ln -s "$(uv python find 3.12)" /usr/local/bin/python3
COPY --chmod=0755 bk-claude-turn /usr/local/bin/bk-claude-turn
USER actor
ENV CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 \
    DISABLE_AUTOUPDATER=1 \
    CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 \
    OPENSPEC_TELEMETRY=0 \
    CLAUDE_CONFIG_DIR=/home/actor/.claude \
    UV_PYTHON_DOWNLOADS=never \
    HOME=/home/actor
WORKDIR /work
CMD ["claude", "--version"]
