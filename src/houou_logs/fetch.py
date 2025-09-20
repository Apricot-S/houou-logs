# SPDX-FileCopyrightText: 2025 Apricot S.
# SPDX-License-Identifier: MIT
# This file is part of https://github.com/Apricot-S/houou-logs

from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

import requests

from . import db

MIN_FETCH_INTERVAL = timedelta(minutes=20)

URL_LATEST = "https://tenhou.net/sc/raw/list.cgi"
URL_OLD = "https://tenhou.net/sc/raw/list.cgi?old"

TIMEOUT = (
    5.0,  # connect timeout
    5.0,  # read timeout
)


def should_fetch(
    last_fetch_time: datetime,
    *,
    now: datetime | None = None,
) -> bool:
    if now is None:
        now = datetime.now(tz=UTC)

    return now - last_fetch_time > MIN_FETCH_INTERVAL


def fetch_file_index_text(session: requests.Session, url: str) -> str:
    res = session.get(url, timeout=TIMEOUT)
    res.raise_for_status()
    return res.text


# ### 1. 最新7日間から取得する場合
# - **1-1**: 「最新7日間から取得する」かどうかの判定ロジックを関数化
# - **1-2**: 「最後にアーカイブを取得した時間」を DB から取得する処理を関数化
# - **1-3**: 「取得時間が現在の20分以内かどうか」を判定する関数
# - **1-4**: 判定結果が True の場合に「メッセージを出して終了する」処理（UI/ログ出力）
#
# ### 3. 天鳳の API から FileIndex を取得する
# - **3-1**: API の URL を生成する関数
# - **3-2**: HTTP リクエストを送信する関数（タイムアウトやリトライは別関数に）
# - **3-3**: レスポンスをパースして FileIndex の構造体／辞書に変換する関数
#
# ### 4. File がすべて取得済みかつサイズが増えていないものを対象外にする
# - **4-1**: DB から既存ファイルの名前とサイズを取得する関数
# - **4-2**: FileIndex の各エントリと DB の記録を比較する関数
# - **4-3**: 「取得済みかつサイズ変化なし」かどうかを判定する関数
#
# ### 5. 対象のファイルの URL リストを作成する
# - **5-1**: FileIndex のエントリから URL を生成する関数
# - **5-2**: 対象外を除外して URL リストを返す関数
#
# ### 6. ダウンロードする一時ディレクトリを作成する
# - **6-1**: 一時ディレクトリのパスを決定する関数
# - **6-2**: ディレクトリを作成する関数（既存ならスキップ）
#
# ### 7. ファイルを1つダウンロードする
# - **7-1**: URL からファイル名を決定する関数
# - **7-2**: HTTP でファイルを取得する関数
# - **7-3**: 取得したバイト列をファイルに保存する関数
#
# ### 8. extract_log_entries() で対局IDリストを抽出する
# - **8-1**: ファイルを読み込む関数
# - **8-2**: ログ形式をパースして対局IDを抽出する関数
#
# ### 9. insert_entries で対局IDリストを DB に追加する
# - **9-1**: DB 接続を開く関数
# - **9-2**: 対局IDリストを INSERT する関数（重複排除は別関数に）
#
# ### 10. 追加が完了したらそのファイルの名前とファイルサイズを DB に追記する
# - **10-1**: ファイルサイズを取得する関数
# - **10-2**: ファイル名とサイズを DB に INSERT/UPDATE する関数
def fetch(db_path: str | Path, *, archive: bool) -> int:
    num_logs = 0
    with closing(db.open_db(db_path)) as conn, conn:
        db.setup_table(conn)
        cursor = conn.cursor()

        if not archive:
            last_fetch_time = db.get_last_fetch_time(cursor)
            if not should_fetch(last_fetch_time):
                return -1

        index_url = URL_OLD if archive else URL_LATEST

    return num_logs
