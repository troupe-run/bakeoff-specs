# Commits (1, newest first)

Each commit's short SHA and subject, then its message body.

## a568313 Add remote (https/http) includes and a JSON Schema for the configuration

Remote includes are fetched on load and are read-only: a change to a value
from one exits 3 and names the include line in the local file. The schema at
.troupe/troupe.schema.json validates the loaded configuration and marks
format: uri strings as literals; a !literal tag does the same. set writes
include-like strings tagged !literal unless --include is given.

