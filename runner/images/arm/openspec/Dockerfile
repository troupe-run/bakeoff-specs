# runner/images/arm/openspec/Dockerfile — transitive deps pinned by package-lock.json (review S-5)
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
COPY package.json package-lock.json /opt/openspec/
RUN cd /opt/openspec && npm ci --omit=dev --no-audit --no-fund && npm cache clean --force \
 && ln -s /opt/openspec/node_modules/.bin/openspec /usr/local/bin/openspec && chmod -R a+rX /opt/openspec
USER actor
