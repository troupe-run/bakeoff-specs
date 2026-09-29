# runner/images/arm/ccsdd/Dockerfile — `npx cc-sdd@3.1.0` runs this same bin; PATH makes `cc-sdd` resolve to it.
# Deviation from the plan text (found building this image, not a design choice): npm always re-runs a local
# directory dependency's "prepare" script on a global install, regardless of --ignore-scripts (long-standing
# npm behaviour, npm/cli#3466-adjacent) — `npm run build` (`tsc -p .`) then fails because devDependencies were
# omitted. cc-sdd@3.1.0 ships its `dist/` prebuilt in the published tarball, so the build is redundant; `jq`
# (already in the base image) strips `scripts` from the vendored copy before the global install so nothing
# tries to rebuild it. `npm ls -g cc-sdd --depth=0 --json` (images.py ARM_VERSION_PROBES) still reports it.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
COPY package.json package-lock.json /opt/ccsdd/
RUN cd /opt/ccsdd && npm ci --omit=dev --no-audit --no-fund && npm cache clean --force \
 && jq 'del(.scripts)' /opt/ccsdd/node_modules/cc-sdd/package.json > /tmp/cc-sdd-package.json \
 && mv /tmp/cc-sdd-package.json /opt/ccsdd/node_modules/cc-sdd/package.json \
 && chmod -R a+rX /opt/ccsdd \
 && npm install -g --offline --no-audit --no-fund /opt/ccsdd/node_modules/cc-sdd
USER actor
