# mjlog parsing example

`split_log_to_game_rounds.py` splits exported mjlog XML into rounds.

Place a local XML file at `examples/log.xml`, then run from the repository
root:

```sh
python examples/split_log_to_game_rounds.py
```

The default input is resolved relative to the script. To use another file,
pass its path (relative paths are resolved from the working directory):

```sh
python examples/split_log_to_game_rounds.py path/to/log.xml
```

The script prints a JSON list of rounds, each containing XML strings.

- Every returned round starts with `INIT`. Multiple `AGARI` elements
  (for example, a double ron) stay in the same round until the next `INIT`.
- `AGARI` or `RYUUKYOKU` with an `owari` attribute ends the game.
- Metadata tags (`SHUFFLE`, `GO`, `TAIKYOKU`) are skipped, and legacy
  `shuffle` attributes on `INIT` are removed.
- Participant and connection tags (`UN` / `BYE`) before the first `INIT`
  are omitted. Within a round, they are preserved in their original order.
- After game end, `UN` / `BYE` are allowed but omitted; other tags are
  rejected.
- Round events before the first `INIT` and logs without a final `owari`
  are rejected.

This example splits rounds; it does not fully validate mahjong rules or
every event sequence.
