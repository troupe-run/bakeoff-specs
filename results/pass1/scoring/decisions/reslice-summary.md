# Decision reslice: behaviour groups

Per topic: how many arms fell in each behaviour group, per question and per route. No arm is named. "none" means no group fitted; such an arm keeps its route's rating.

## T7

- T7 Q1 (history order when one block replaces another): SET_FIRST 5, SWAP 1
  - Route 1: SET_FIRST 1
  - Route 2: SET_FIRST 4, SWAP 1

## T8

- T8 Q1 (does config show keep the !literal mark): KEEP 2, DROP 4
  - Route 1: DROP 1
  - Route 2: KEEP 2, DROP 3

## T10

- T10 Q1 (error when both troupe.yml and troupe.yaml exist (all exit 4)): FIX 2, PROBLEM 4
  - Route 1: PROBLEM 2
  - Route 2: FIX 2, PROBLEM 2

## T11

- T11 Q1 (single-newline value config set e "\n"): BLOCK 3, QUOTED 1, QUOTED_MISMATCH 1, REFUSE 1
  - Route 1: BLOCK 2, QUOTED 1, QUOTED_MISMATCH 1, REFUSE 1
  - Route 2: BLOCK 1

## T13

- T13 Q1 (comment column when a value's length changes): KEEP 5, DRIFT 1
  - Route 1: KEEP 4, DRIFT 1
  - Route 2: KEEP 1

## T15

- T15 Q1 (replacing a list entry whose first key is on the dash line): REFUSE 1, WRITE_KEEP 3, WRITE_STRIP 2
  - Route 1: REFUSE 1
  - Route 2: WRITE_KEEP 1
  - Route 3: WRITE_KEEP 2, WRITE_STRIP 2

## T16

- T16 Q1 (error for complex (non-scalar) keys; every arm refuses with exit 4): FILE_LINE 2, FILE 3, NEITHER 1
  - Route 1: FILE 2, NEITHER 1
  - Route 2: FILE_LINE 2, FILE 1

## T20

- T20 Q1 (duplicate key in the file): RAISE 3, LAST 2, FIRST_DISAGREE 1
  - Route 1: RAISE 2
  - Route 2: RAISE 1, LAST 2, FIRST_DISAGREE 1

## T25

- T25 Q1 (wording of the out-of-range list index error (exit codes identical)): FIX 2, FACTS 2, BARE 2
  - Route 1: FIX 1, FACTS 1, BARE 2
  - Route 2: FIX 1, FACTS 1

## T26

- T26 Q1 (a file: value given to set): DROP 4, KEEP_EXIT3 1, KEEP_EXIT4 1
  - Route 1: DROP 1
  - Route 2: DROP 3
  - Route 3: KEEP_EXIT3 1, KEEP_EXIT4 1

## T27

- T27 Q1 (replacing an inline collection): BLOCK 1, INLINE_GAP 4, INLINE_KEPT 1
  - Route 1: BLOCK 1
  - Route 2: INLINE_GAP 1
  - Route 3: INLINE_GAP 3, INLINE_KEPT 1

## T33

- T33 Q1 (escaping in history output): ASCII 1, READABLE 5
  - Route 1: ASCII 1
  - Route 2: READABLE 1
  - Route 3: READABLE 4
- T33 Q2 (U+2028 written to the config file): ESCAPED 2, RAW_QUOTED 2, RAW_UNQUOTED 2
  - Route 1: RAW_UNQUOTED 1
  - Route 2: RAW_QUOTED 1
  - Route 3: ESCAPED 2, RAW_QUOTED 1, RAW_UNQUOTED 1

## T34

- T34 Q1 (history after the config breaks its schema): WORKS 2, FAILS 4
  - Route 1: WORKS 1
  - Route 2: FAILS 2
  - Route 3: WORKS 1, FAILS 2

## T36

- T36 Q1 (include cycle refused on write): EXIT3 5, EXIT4 1
  - Route 1: EXIT3 2, EXIT4 1
  - Route 2: EXIT3 3

## T46

- T46 Q1 (refusing a key longer than 1024 characters): A 4, B 1, C 1
  - Route 1: A 1, B 1
  - Route 2: A 3, C 1

## T47

- T47 Q1 (malformed PATH error wording (all exit 2)): RULE 1, PROBLEM 3, BARE 2
  - Route 1: RULE 1, PROBLEM 1
  - Route 2: PROBLEM 2, BARE 2

## T48

- T48 Q1 (a set that changes troupe.yml and a file: prompt): A 4, B 2
  - Route 1: A 1, B 2
  - Route 2: A 1
  - Route 3: A 2

## T50

- T50 Q1 (quoting when config set replaces a section and drops its last entry): A 1, B 3, C 2
  - Route 1: A 1, B 2
  - Route 2: B 1, C 2

## T51

- T51 Q1 (state left behind after a failed config load): A 4, B 1, C 1
  - Route 1: A 4, B 1
  - Route 2: C 1

## T57

- T57 Q1 (where the replacing set goes among remove events): A 5, B 1
  - Route 1: A 1
  - Route 2: A 2, B 1
  - Route 3: A 1
  - Route 4: A 1

## T59

- T59 Q1 (a non-mapping root file (~, ---, a scalar, a list)): A 2, B 4
  - Route 1: A 2, B 3
  - Route 2: B 1

## T61

- T61 Q1 (a commented list item replaced by a map or list): A 4, B 2
  - Route 1: A 2, B 2
  - Route 2: A 2

## T66

- T66 Q1 (writing into a file that two agents include): W 3, R1 1, R2 2
  - Route 1: W 1
  - Route 2: W 1
  - Route 3: R1 1, R2 1
  - Route 4: W 1, R2 1

## T68

- T68 Q1 (how exponent floats are written to the file): P 3, N 3
  - Route 1: P 2, N 1
  - Route 2: P 1, N 2

## T70

- T70 Q1 (source naming with show --sources when a file is reached through a symlink): R 3, L 2, S 1
  - Route 1: R 2, L 2, S 1
  - Route 2: R 1
- T70 Q2 (config set through a symlinked theatre): G 3, H 1, F 2
  - Route 1: G 2, H 1, F 2
  - Route 2: G 1

## T73

- T73 Q1 (a corrupt history store): T 2, U 4
  - Route 1: U 3
  - Route 2: T 2, U 1

## T74

- T74 Q1 (what is left in .troupe): A 3, B 2, C 1
  - Route 1: A 2
  - Route 2: A 1, B 2, C 1

## T78

- T78 Q1 (where --theatre is accepted): ANYWHERE 1, TWO 2, SUB_ONLY 3
  - Route 1: TWO 1
  - Route 2: SUB_ONLY 3
  - Route 3: ANYWHERE 1, TWO 1

## T81

- T81 Q1 (how non-string scalars are spelled when written): K 3, C 3
  - Route 1: C 2
  - Route 2: K 2
  - Route 3: K 1, C 1

## T82

- T82 EMPTY (set empty ""): REFUSE 2, NULL 4
  - Route 1: NULL 1
  - Route 2: REFUSE 2, NULL 1
  - Route 3: NULL 2
- T82 BLOCK (set block "a: b"): REFUSE 2, REFUSE_NOFIX 3, MAP 1
  - Route 1: MAP 1
  - Route 2: REFUSE 1, REFUSE_NOFIX 2
  - Route 3: REFUSE 1, REFUSE_NOFIX 1
- T82 TAG (set tagged "!!str 5"): HONOUR 2, REFUSE 2, NUMBER 2
  - Route 1: NUMBER 1
  - Route 2: HONOUR 1, REFUSE 1, NUMBER 1
  - Route 3: HONOUR 1, REFUSE 1
- T82 ANCHOR (set anchored "&n 1"): REFUSE 3, DROP 3
  - Route 1: DROP 1
  - Route 2: REFUSE 1, DROP 2
  - Route 3: REFUSE 2

## T87

- T87 Q1 (watch's stderr report of a broken hand edit): A 3, D 2, X 1
  - Route 1: A 3, D 1
  - Route 2: D 1, X 1

## T96

- T96 Q1 (re-wrapping when unchanged paragraphs are only reordered): K 1, W 5
  - Route 1: K 1, W 5

## T99

- T99 Q1 (indentation of new list items in a file with flush lists): F 4, I 2
  - Route 1: F 4, I 2

## T117

- T117 Q1 (stopping watch with SIGINT/SIGTERM): C 2, S 3, K 1
  - Route 1: C 2, S 3, K 1
