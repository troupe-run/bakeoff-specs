# runner/images/arm/speckitty/Dockerfile — 3.2.7 stable, never the 4.0 RC line (design §2); beads from its lockfile.
# @beads/bd's postinstall downloads its native binary from GitHub releases with no checksum of its own
# (fix-round-1 item 1): BD_SHA256 (pinned by `runner images pin` against the actual binary next to the JS
# wrapper, not the wrapper) is verified here with `sha256sum -c`, failing the build on any mismatch.
# HOME is /root while building as root (fix-round-1 item 2): the base image bakes ENV HOME=/home/actor, so
# without this, `uv venv`/`npm ci`/@beads/bd's postinstall self-test (`bd version`) all write root-owned
# cache/config debris into /home/actor — breaking `uv venv`/etc for `actor` at runtime with no home mount.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
ARG BD_SHA256
USER root
ENV HOME=/root
COPY requirements.txt /opt/speckitty-requirements.txt
COPY package.json package-lock.json /opt/beads/
RUN UV_PYTHON_DOWNLOADS=never uv venv --python 3.12 /opt/venvs/speckitty \
 && uv pip install --python /opt/venvs/speckitty/bin/python --require-hashes -r /opt/speckitty-requirements.txt \
 && ln -s /opt/venvs/speckitty/bin/spec-kitty /usr/local/bin/spec-kitty \
 && cd /opt/beads && npm ci --omit=dev --no-audit --no-fund && npm cache clean --force \
 && BD_BIN="$(dirname "$(readlink -f /opt/beads/node_modules/@beads/bd/bin/bd.js)")/bd" \
 && echo "${BD_SHA256}  ${BD_BIN}" | sha256sum -c - \
 && ln -s /opt/beads/node_modules/.bin/bd /usr/local/bin/bd && chmod -R a+rX /opt/venvs /opt/beads
USER actor
ENV HOME=/home/actor
