# runner/images/arm/speckit/Dockerfile — hash-locked (review S-5)
# HOME is /root while building as root (fix-round-1 item 2): the base image bakes ENV HOME=/home/actor, so
# without this, `uv venv`/`uv pip install` write root-owned `.cache/uv` debris into /home/actor, breaking
# `uv venv` for `actor` at runtime (`Permission denied` opening the root-owned cache) with no home mount.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
ENV HOME=/root
COPY requirements.txt /opt/speckit-requirements.txt
RUN UV_PYTHON_DOWNLOADS=never uv venv --python 3.12 /opt/venvs/speckit \
 && uv pip install --python /opt/venvs/speckit/bin/python --require-hashes -r /opt/speckit-requirements.txt \
 && ln -s /opt/venvs/speckit/bin/specify /usr/local/bin/specify && chmod -R a+rX /opt/venvs
USER actor
ENV HOME=/home/actor
