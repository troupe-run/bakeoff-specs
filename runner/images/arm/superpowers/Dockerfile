# runner/images/arm/superpowers/Dockerfile — OD9 B: the plugin at its tag's verified commit, vendored read-only.
# .git is stripped from the copied tree (fix-round-1 item 7): the shallow clone's own .git has no business
# inside the vendored plugin the arm sees, and PLUGIN_0_SUBDIR="" (the plugin root is the whole repo) means
# `cp -r` would otherwise carry it straight in.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
ARG PLUGIN_0_NAME
ARG PLUGIN_0_REPO
ARG PLUGIN_0_TAG
ARG PLUGIN_0_SHA
ARG PLUGIN_0_SUBDIR
USER root
RUN git clone --quiet --depth 1 --branch "${PLUGIN_0_TAG}" "https://github.com/${PLUGIN_0_REPO}" /tmp/p0 \
 && test "$(git -C /tmp/p0 rev-parse HEAD)" = "${PLUGIN_0_SHA}" \
 && mkdir -p /opt/plugins && cp -r "/tmp/p0/${PLUGIN_0_SUBDIR}" "/opt/plugins/${PLUGIN_0_NAME}" \
 && rm -rf "/opt/plugins/${PLUGIN_0_NAME}/.git" \
 && test -f "/opt/plugins/${PLUGIN_0_NAME}/.claude-plugin/plugin.json" \
 && rm -rf /tmp/p0 && chmod -R a+rX /opt/plugins
USER actor
