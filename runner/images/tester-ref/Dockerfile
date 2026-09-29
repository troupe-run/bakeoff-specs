# runner/images/tester-ref/Dockerfile — the tester plus the reference implementation, for the harness's OWN
# reference runs only (flake-vs-reference classification, review C-2). No arm code ever runs in this image
# (runner/hidden.py refuses an arm copy for it; Task 18 fix round 3). Built with the REPO ROOT as context.
ARG TESTER_IMAGE
FROM ${TESTER_IMAGE}
USER root
COPY reference /opt/reference
# Belt and braces: 1000-owned, 0700, no build cache left behind.
RUN cd /opt/reference && rm -rf .venv \
 && UV_PYTHON_DOWNLOADS=never UV_CACHE_DIR=/tmp/uv-build-cache uv sync --frozen --no-dev \
 && rm -rf /tmp/uv-build-cache \
 && chown -R 1000:1000 /opt/reference && chmod -R go-rwx /opt/reference && chmod 0700 /opt/reference
USER actor
