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
`INIT` starts a round; `AGARI` or `RYUUKYOKU` with an `owari` attribute
ends the game. Metadata tags are skipped and legacy `shuffle` attributes
on `INIT` are removed.
