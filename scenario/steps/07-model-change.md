# Step 7 — remote includes and a schema

- Includes can now point at `https://` URLs (shared team configuration). They are read-only from troupe's
  point of view: refuse changes to their values, and tell the user which include line to change instead.
- The configuration is described by a JSON Schema at `.troupe/troupe.schema.json`. Some settings are URLs
  that must never be treated as includes; the schema marks those with `"format": "uri"`, and a `!literal` tag
  marks any other value that must be taken literally.

The CLI contract sections in force are listed below; the full contract is attached.

Contract sections in force: General; Includes; set PATH VALUE; history [PATH]; Sync with files; get and show; Lineage; Overrides; Aliases; Remote includes and schema (from step 7).
