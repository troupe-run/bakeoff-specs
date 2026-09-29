# runner/images/arm/speckit/Dockerfile — hash-locked (review S-5)
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
COPY requirements.txt /opt/speckit-requirements.txt
RUN UV_PYTHON_DOWNLOADS=never uv venv --python 3.12 /opt/venvs/speckit \
 && uv pip install --python /opt/venvs/speckit/bin/python --require-hashes -r /opt/speckit-requirements.txt \
 && ln -s /opt/venvs/speckit/bin/specify /usr/local/bin/specify && chmod -R a+rX /opt/venvs
USER actor
