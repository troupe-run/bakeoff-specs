# runner/images/dryrun/Dockerfile — built with the repo root as context (Task 24 adds COPY reference)
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
COPY --chmod=0755 runner/images/dryrun/fake_claude.py /usr/local/bin/claude
USER actor
