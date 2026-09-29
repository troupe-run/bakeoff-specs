# runner/images/arm/speckitty/Dockerfile — 3.2.7 stable, never the 4.0 RC line (design §2); beads from its lockfile.
# @beads/bd downloads its binary in postinstall; the binary's SHA-256 is recorded in images.lock.json (bd-sha256).
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
COPY requirements.txt /opt/speckitty-requirements.txt
COPY package.json package-lock.json /opt/beads/
RUN UV_PYTHON_DOWNLOADS=never uv venv --python 3.12 /opt/venvs/speckitty \
 && uv pip install --python /opt/venvs/speckitty/bin/python --require-hashes -r /opt/speckitty-requirements.txt \
 && ln -s /opt/venvs/speckitty/bin/spec-kitty /usr/local/bin/spec-kitty \
 && cd /opt/beads && npm ci --omit=dev --no-audit --no-fund && npm cache clean --force \
 && ln -s /opt/beads/node_modules/.bin/bd /usr/local/bin/bd && chmod -R a+rX /opt/venvs /opt/beads
USER actor
