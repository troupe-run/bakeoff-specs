# runner/images/tester/Dockerfile — runs hidden tests and quality tools; never runs Claude.
# Arm code runs in this image (prep: the arm's build backend; tests: the arm's CLI), so it holds NO reference
# implementation (Task 18 fix round 3). The reference lives only in runner/images/tester-ref, used only by the
# harness's own reference runs. Built with the REPO ROOT as context.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
COPY runner/images/tester/requirements.txt runner/images/tester/mutmut-requirements.txt /opt/
RUN UV_PYTHON_DOWNLOADS=never uv venv --python 3.12 /opt/harness \
 && uv pip install --python /opt/harness/bin/python --require-hashes -r /opt/requirements.txt \
 && chmod -R a+rX /opt/harness /opt/mutmut-requirements.txt
USER actor
ENV PYTHONDONTWRITEBYTECODE=1 UV_NO_SYNC=1
