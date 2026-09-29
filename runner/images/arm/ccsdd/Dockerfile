# runner/images/arm/ccsdd/Dockerfile — `npx cc-sdd@3.1.0` runs this same bin; PATH makes `cc-sdd` resolve to it.
# Plain symlink into node_modules/.bin, same pattern as openspec (fix-round-1 item 6): an earlier version of
# this Dockerfile ran `npm install -g` on the local node_modules/cc-sdd path, which re-triggers npm's
# "prepare" lifecycle (`npm run build` → `tsc -p .`) regardless of --ignore-scripts — a long-standing npm
# behaviour for local/git dependencies — and failed because devDependencies were correctly omitted. The
# symlink needs no global install and no lifecycle scripts at all; re-verified offline (`--network none`)
# that `cc-sdd --claude-skills --lang en --yes` in a scratch project still writes the documented 50 files
# (task-3-report.md, fix round 1). Version probe: `cc-sdd --version` (images.py cc_sdd_version), not
# `npm ls -g`, since cc-sdd is no longer a global npm package here.
# HOME is /root while building as root (fix-round-1 item 2): the base image bakes ENV HOME=/home/actor, so
# without this, `npm ci` writes root-owned `.npm` debris into /home/actor.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
ENV HOME=/root
COPY package.json package-lock.json /opt/ccsdd/
RUN cd /opt/ccsdd && npm ci --omit=dev --no-audit --no-fund && npm cache clean --force \
 && ln -s /opt/ccsdd/node_modules/.bin/cc-sdd /usr/local/bin/cc-sdd && chmod -R a+rX /opt/ccsdd
USER actor
ENV HOME=/home/actor
