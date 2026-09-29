# runner/images/arm/openspec/Dockerfile — transitive deps pinned by package-lock.json (review S-5)
# HOME is /root while building as root (fix-round-1 item 2): the base image bakes ENV HOME=/home/actor, so
# without this, `npm ci` writes root-owned `.npm` debris into /home/actor.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
ENV HOME=/root
COPY package.json package-lock.json /opt/openspec/
RUN cd /opt/openspec && npm ci --omit=dev --no-audit --no-fund && npm cache clean --force \
 && ln -s /opt/openspec/node_modules/.bin/openspec /usr/local/bin/openspec && chmod -R a+rX /opt/openspec
USER actor
ENV HOME=/home/actor
