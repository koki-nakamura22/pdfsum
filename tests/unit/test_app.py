"""CLI (digestkit ベース) のスモークテスト。

実際の LLM 呼び出しを伴う ``summarize`` サブコマンドは外部 API 依存のため
ここでは検証せず (e2e ドッグフーディングで確認)、digestkit が書く
``digests`` テーブルを前提とする ``list`` / ``show`` / ``delete`` の
3 サブコマンド + パース層に絞ってテストする。
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest

from pdfsum.cli import app
from pdfsum.cli.app import _build_parser, main
from pdfsum.config.manager import Config


@pytest.fixture
def populated_db(tmp_path: Path) -> Iterator[Path]:
    """digestkit ``SQLiteSink`` 互換のレコードを投入した DB を返す。"""
    db = tmp_path / "digests.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE digests ("
        "item_id TEXT, summary TEXT, tokens_in INT, tokens_out INT, "
        "latency_ms INT, model TEXT, created_at TEXT)"
    )
    conn.executemany(
        "INSERT INTO digests VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (
                "/tmp/papers/alpha.pdf",
                "alpha summary",
                100,
                30,
                500,
                "claude-haiku",
                "2026-05-09T10:00:00",
            ),
            (
                "/tmp/papers/beta.pdf",
                "beta summary",
                200,
                40,
                600,
                "claude-haiku",
                "2026-05-09T11:00:00",
            ),
        ],
    )
    conn.commit()
    conn.close()
    yield db


def test_parser_has_four_subcommands() -> None:
    parser = _build_parser()
    actions = [a for a in parser._actions if a.dest == "command"]
    assert actions
    choices = set(actions[0].choices or {})
    assert choices == {"summarize", "list", "show", "delete"}


def test_list_empty_db(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "missing.db"
    rc = main(["list", "--db-path", str(db)])
    assert rc == 0
    assert "保存済みの要約はありません" in capsys.readouterr().out


def test_list_shows_rows(
    populated_db: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(["list", "--db-path", str(populated_db)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "alpha.pdf" in out
    assert "beta.pdf" in out
    # 既定では絶対パスは出さず basename だけ
    assert "/tmp/papers/" not in out


def test_list_full_id(
    populated_db: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(["list", "--full-id", "--db-path", str(populated_db)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "/tmp/papers/alpha.pdf" in out


def test_show_resolves_basename(
    populated_db: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(["show", "alpha", "--db-path", str(populated_db)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "alpha summary" in out
    assert "claude-haiku" in out


def test_show_not_found(
    populated_db: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(["show", "missing", "--db-path", str(populated_db)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "見つかりません" in err


def test_show_escapes_like_wildcards(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = tmp_path / "digests.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE digests ("
        "item_id TEXT, summary TEXT, tokens_in INT, tokens_out INT, "
        "latency_ms INT, model TEXT, created_at TEXT)"
    )
    conn.executemany(
        "INSERT INTO digests VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (
                "/tmp/papers/a_b.pdf",
                "literal underscore",
                100,
                20,
                300,
                "claude-haiku",
                "2026-05-09T10:00:00",
            ),
            (
                "/tmp/papers/acb.pdf",
                "wildcard match candidate",
                100,
                20,
                300,
                "claude-haiku",
                "2026-05-09T11:00:00",
            ),
        ],
    )
    conn.commit()
    conn.close()

    rc = main(["show", "a_b", "--db-path", str(db)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "literal underscore" in out
    assert "wildcard match candidate" not in out


def test_delete_removes_row(
    populated_db: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = main(["delete", "alpha", "--db-path", str(populated_db)])
    assert rc == 0
    # 削除メッセージ自体に "alpha" が出るので、ここで一度バッファを切る
    capsys.readouterr()
    rc2 = main(["list", "--db-path", str(populated_db)])
    assert rc2 == 0
    out = capsys.readouterr().out
    assert "alpha.pdf" not in out
    assert "beta.pdf" in out


def test_delete_clears_seen_store(
    populated_db: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    seen_db = app._seen_store_path()
    seen_db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(seen_db)
    conn.execute(
        "CREATE TABLE seen_items (item_id TEXT PRIMARY KEY, added_at TEXT)"
    )
    conn.execute(
        "INSERT INTO seen_items VALUES (?, ?)",
        ("/tmp/papers/alpha.pdf", "2026-05-09T10:00:00"),
    )
    conn.commit()
    conn.close()

    rc = main(["delete", "alpha", "--db-path", str(populated_db)])
    assert rc == 0

    conn = sqlite3.connect(seen_db)
    row = conn.execute(
        "SELECT 1 FROM seen_items WHERE item_id = ?",
        ("/tmp/papers/alpha.pdf",),
    ).fetchone()
    conn.close()
    assert row is None


def test_list_reports_sqlite_operational_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    db = tmp_path / "digests.db"
    db.touch()

    class BrokenConnection:
        row_factory: object | None = None

        def execute(
            self, _sql: str, _params: tuple[object, ...] = ()
        ) -> sqlite3.Cursor:
            raise sqlite3.OperationalError("database is locked")

        def close(self) -> None:
            return None

    monkeypatch.setattr(app.sqlite3, "connect", lambda _path: BrokenConnection())

    rc = main(["list", "--db-path", str(db)])
    assert rc == 1
    assert "SQLite 読み取りに失敗しました" in capsys.readouterr().err


def test_summarize_file_uses_parent_dir_and_filename_glob(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.7")
    captured: dict[str, object] = {}

    def fake_load(self: object) -> Config:
        return Config()

    def fake_build_digester(
        source_path: Path,
        *,
        glob: str,
        db_path: Path,
        config: Config,
    ) -> object:
        captured["source_path"] = source_path
        captured["glob"] = glob
        captured["db_path"] = db_path
        captured["config"] = config

        class DummyDigester:
            def run(
                self, limit: int | None = None, dry_run: bool = False
            ) -> object:
                captured["limit"] = limit
                captured["dry_run"] = dry_run
                return SimpleNamespace(success=1, skipped=0, failures=[])

        return DummyDigester()

    monkeypatch.setattr(app.ConfigManager, "load", fake_load)
    monkeypatch.setattr(app, "_build_digester", fake_build_digester)

    rc = main(
        [
            "summarize",
            str(pdf),
            "--db-path",
            str(tmp_path / "out.db"),
            "--limit",
            "3",
            "--dry-run",
        ]
    )

    assert rc == 0
    assert captured["source_path"] == pdf.parent
    assert captured["glob"] == pdf.name
    assert captured["db_path"] == tmp_path / "out.db"
    assert captured["limit"] == 3
    assert captured["dry_run"] is True
    assert "完了: success=1 skipped=0 failures=0" in capsys.readouterr().out


def test_summarize_directory_uses_user_glob(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target_dir = tmp_path / "papers"
    target_dir.mkdir()
    captured: dict[str, object] = {}

    def fake_load(self: object) -> Config:
        return Config()

    def fake_build_digester(
        source_path: Path,
        *,
        glob: str,
        db_path: Path,
        config: Config,
    ) -> object:
        captured["source_path"] = source_path
        captured["glob"] = glob

        class DummyDigester:
            def run(
                self, limit: int | None = None, dry_run: bool = False
            ) -> object:
                return SimpleNamespace(success=0, skipped=0, failures=[])

        return DummyDigester()

    monkeypatch.setattr(app.ConfigManager, "load", fake_load)
    monkeypatch.setattr(app, "_build_digester", fake_build_digester)

    rc = main(["summarize", str(target_dir), "--glob", "**/*.PDF"])

    assert rc == 0
    assert captured["source_path"] == target_dir
    assert captured["glob"] == "**/*.PDF"


def test_build_digester_overrides_standard_env_var_with_resolved_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("OPENAI_API_KEY", "stale-key")
    config = Config()
    config.llm.provider = "openai"
    config.llm.model = "gpt-4.1-mini"
    config.llm.providers["openai"].api_key_env = "PDFSUM_OPENAI_KEY"
    monkeypatch.setenv("PDFSUM_OPENAI_KEY", "fresh-key")

    digester = app._build_digester(
        tmp_path,
        glob="*.pdf",
        db_path=tmp_path / "digests.db",
        config=config,
    )

    assert digester is not None
    assert app.os.environ["OPENAI_API_KEY"] == "fresh-key"


def test_no_command_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main([])
    assert rc == 2
    assert "pdfsum" in capsys.readouterr().out
