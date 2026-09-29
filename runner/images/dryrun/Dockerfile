# runner/images/dryrun/Dockerfile — built with the repo root as context. The dry-run arm is a harness SELF-TEST arm,
# never an arm under test: its fake claude plays the arm with the reference implementation (Task 24), so the
# reference is baked in here, at /opt/reference, readable by the actor. Real arm images never contain it.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
COPY reference /opt/reference
RUN rm -rf /opt/reference/.venv && find /opt/reference -name __pycache__ -prune -exec rm -rf {} + \
 && chmod -R a+rX /opt/reference
COPY --chmod=0755 runner/images/dryrun/fake_claude.py /usr/local/bin/claude
USER actor
