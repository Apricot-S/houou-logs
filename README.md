# houou-logs

Tools to download houou (phoenix) logs from tenhou.net

## Installation

```sh
# With pip.
houou-logs$ pip install .
# With uv.
houou-logs$ uv tool install .
```

## Usage

### Extract log IDs from archive (per year)

```sh
houou-logs extract <db-path> <archive-path>
```

Example:

```sh
houou-logs extract db/2024.db scraw2024.zip
```

### Fetch latest log IDs

```sh
houou-logs fetch <db-path> [--start]
```

Example:

```sh
houou-logs fetch db/latest.db
```

```sh
houou-logs fetch db/latest.db --start
```

### Fetch yakuman log IDs

```sh
houou-logs yakuman <db-path> [--year <n>] [--month <n>]
```

Example:

```sh
houou-logs yakuman db/yakuman/2006/10.db --year 2006 --month 10
```

### Fetch log contents

```sh
houou-logs fetch-logs <db-path> [--limit <n>]
```

Example:

```sh
houou-logs fetch-logs db/2024.db --limit 50
```

### Validate that fetched logs can be parsed

```sh
houou-logs validate <db-path>
```

Example:

```sh
houou-logs validate db/2024.db
```

### Export raw log contents (xml) from DB

```sh
houou-logs export <db-path> <output-dir> [--players <4 or 3>] [--length <t or h>] [--limit <n>] [--offset <n>]
```

Example:

```sh
houou-logs export db/2024.db xml/2024/4p/hanchan --players 4 --length h --limit 100 --offset 50
```

## Credits

This project is heavily inspired by:

- [phoenix-logs](https://github.com/MahjongRepository/phoenix-logs), created by [Aleksei Lisikhin](https://github.com/Nihisil).

## License

Copyright (c) Apricot S. All rights reserved.

Licensed under the [MIT license](LICENSE).
