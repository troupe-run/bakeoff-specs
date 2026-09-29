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
RUN cd /opt/reference && rm -rf .venv && UV_PYTHON_DOWNLOADS=never uv sync --frozen --no-dev \
 && chmod -R a+rX /opt/reference
USER actor
ENV PYTHONDONTWRITEBYTECODE=1 UV_NO_SYNC=1
