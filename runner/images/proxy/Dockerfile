# runner/images/proxy/Dockerfile — egress allowlist proxy sidecar (prior art: ../spike-claude-docker/proxy/).
# Every FROM is by digest (review S-5); the tinyproxy apk version is pinned too (review m1), since apk
# packages have no content digest to pin against directly.
ARG ALPINE_IMAGE
FROM ${ALPINE_IMAGE}
ARG TINYPROXY_VERSION
RUN apk add --no-cache tinyproxy=${TINYPROXY_VERSION}
COPY tinyproxy.conf /etc/tinyproxy/tinyproxy.conf
USER nobody
EXPOSE 3128
CMD ["tinyproxy", "-d", "-c", "/etc/tinyproxy/tinyproxy.conf"]
