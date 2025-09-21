# houou-logs

Tools to download Houou (Phoenix) logs from tenhou.net

## Installation

```sh
# With pip.
houou-logs$ pip install .
# With uv.
houou-logs$ uv tool install .
```

## Usage

### Import log IDs from an archive (per year)

Import a list of log IDs into the database.

> [!NOTE]
> Houou (Phoenix) games are available starting from 2009.

```sh
houou-logs import <db-path> <archive-path>
```

Example:

Import log IDs for the year 2009.

1. Download the archive file manually: `https://tenhou.net/sc/raw/scraw2009.zip`
2. Place the file in the current working directory.
3. Run:

```sh
houou-logs import db/2009.db scraw2009.zip
```

### Fetch latest log IDs

Fetch a list of log IDs into the database.

This command skips log files that are already fetched and have the same size, and only adds new log IDs to the database.

#### Fetch log IDs from the latest 7 days (default mode)

> [!NOTE]
> In this mode, if executed again within 20 minutes from the last run, the process will be cancelled because there are no updates.

```sh
houou-logs fetch <db-path>
```

Example:

```sh
houou-logs fetch db/latest.db
```

#### Fetch log IDs from January 1 of the current year until 7 days before the current day (archive mode)

```sh
houou-logs fetch <db-path> --archive
```

Example:

```sh
houou-logs fetch db/latest.db --archive
```

### Fetch yakuman log IDs

Fetch log IDs where a yakuman occurred for a specific year and month.

> [!NOTE]
> Yakuman logs are available starting from October 2006.  
> Only four-player game logs are available. Three-player games are not included.  
> Yakuman logs include all tables (four-player only), not just the Houou (Phoenix) table.

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
