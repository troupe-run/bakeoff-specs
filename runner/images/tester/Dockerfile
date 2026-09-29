# runner/images/tester/Dockerfile — runs hidden tests and quality tools; never runs Claude.
# Built with the REPO ROOT as context (it copies reference/ for the flake-vs-reference check, review C-2).
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
COPY runner/images/tester/requirements.txt runner/images/tester/mutmut-requirements.txt /opt/
RUN UV_PYTHON_DOWNLOADS=never uv venv --python 3.12 /opt/harness \
 && uv pip install --python /opt/harness/bin/python --require-hashes -r /opt/requirements.txt \
 && chmod -R a+rX /opt/harness /opt/mutmut-requirements.txt
COPY reference /opt/reference
# The reference is the answer key: only the HARNESS uid (1000) may reach it. Arm code runs in this image as uid 1001
# (runner/hidden.py), so /opt/reference is 1000-owned, 0700 all the way down, and no build cache is left behind
# (Task 18 fix round 2, item 1).
RUN cd /opt/reference && rm -rf .venv \
 && UV_PYTHON_DOWNLOADS=never UV_CACHE_DIR=/tmp/uv-build-cache uv sync --frozen --no-dev \
 && rm -rf /tmp/uv-build-cache \
 && chown -R 1000:1000 /opt/reference && chmod -R go-rwx /opt/reference && chmod 0700 /opt/reference
USER actor
ENV PYTHONDONTWRITEBYTECODE=1 UV_NO_SYNC=1
