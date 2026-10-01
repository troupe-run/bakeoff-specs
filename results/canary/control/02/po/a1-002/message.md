I tightened one thing: what I'd described as "as given" wasn't quite true. `watch` was printing the argument after converting it to a path, which changes some spellings, e.g. `dir/` printed as `dir`. It now prints the `--theatre` argument exactly as typed.

- **Fix:** `watching <dir>` is now byte-for-byte the `--theatre` value. If `--theatre` is left out, it prints the `TROUPE_THEATRE` value, or `.` if that isn't set.
- **Test:** a new test passes `<dir>/./` and checks that the line prints it unchanged. All 32 tests pass.
- **Commit:** `0287ad2` on `main`, not pushed.