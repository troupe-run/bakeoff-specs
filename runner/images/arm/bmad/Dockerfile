# runner/images/arm/bmad/Dockerfile — OD9 B: both BMAD plugins at the verified commit. The plugin roots inside the
# repo are recorded in arms/bmad.toml `subdir` and confirmed by probe P5; a wrong subdir fails the build here.
# PARKED (B2): bmad-plugins carries no tags at all as of 2026-09-29, so v6.12.0 can never resolve and this
# image is never built by `images build_all` (the plugin sha stays empty). .git is stripped from each copied
# subtree regardless (fix-round-1 item 7), for whenever this arm is unparked.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
ARG PLUGIN_0_NAME
ARG PLUGIN_0_REPO
ARG PLUGIN_0_TAG
ARG PLUGIN_0_SHA
ARG PLUGIN_0_SUBDIR
ARG PLUGIN_1_NAME
ARG PLUGIN_1_SUBDIR
USER root
RUN git clone --quiet --depth 1 --branch "${PLUGIN_0_TAG}" "https://github.com/${PLUGIN_0_REPO}" /tmp/p0 \
 && test "$(git -C /tmp/p0 rev-parse HEAD)" = "${PLUGIN_0_SHA}" \
 && mkdir -p /opt/plugins \
 && cp -r "/tmp/p0/${PLUGIN_0_SUBDIR}" "/opt/plugins/${PLUGIN_0_NAME}" \
 && cp -r "/tmp/p0/${PLUGIN_1_SUBDIR}" "/opt/plugins/${PLUGIN_1_NAME}" \
 && rm -rf "/opt/plugins/${PLUGIN_0_NAME}/.git" "/opt/plugins/${PLUGIN_1_NAME}/.git" \
 && test -f "/opt/plugins/${PLUGIN_0_NAME}/.claude-plugin/plugin.json" \
 && test -f "/opt/plugins/${PLUGIN_1_NAME}/.claude-plugin/plugin.json" \
 && rm -rf /tmp/p0 && chmod -R a+rX /opt/plugins
USER actor
