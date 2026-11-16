"""Optional Windows portable PostgreSQL helper; manages only this checkout's tmp/pgdata."""

import argparse
import os
import subprocess
import tempfile
from pathlib import Path

import psycopg
from psycopg import sql

from app.core.config import Settings

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tmp/pgdata"
DEFAULT_BIN = ROOT / "tmp/postgres-tooling/node_modules/@embedded-postgres/windows-x64/native/bin"


def run(command: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        check=check,
        timeout=90,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "stop", "status"])
    parser.add_argument("--bin-dir", type=Path, default=DEFAULT_BIN)
    args = parser.parse_args()
    suffix = ".exe" if os.name == "nt" else ""
    pg_ctl = args.bin_dir / f"pg_ctl{suffix}"
    if not pg_ctl.is_file():
        parser.error("PostgreSQL binaries not found. See the README portable setup instructions.")
    settings = Settings()
    if settings.app_env == "production" or settings.postgres_host != "127.0.0.1":
        parser.error("This helper only supports non-production PostgreSQL on 127.0.0.1")
    DATA.parent.mkdir(parents=True, exist_ok=True)
    if args.action == "stop":
        run([str(pg_ctl), "-D", str(DATA), "-m", "fast", "-w", "stop"])
        return
    if args.action == "status":
        raise SystemExit(run([str(pg_ctl), "-D", str(DATA), "status"], check=False).returncode)
    if not settings.postgres_password.get_secret_value():
        parser.error("Run scripts/init_env.py before starting the database")
    if not (DATA / "PG_VERSION").exists():
        with tempfile.NamedTemporaryFile(mode="w", dir=DATA.parent, delete=False) as temporary:
            temporary.write(settings.postgres_password.get_secret_value())
            password_path = Path(temporary.name)
        try:
            run(
                [
                    str(args.bin_dir / f"initdb{suffix}"),
                    "-D",
                    str(DATA),
                    "-U",
                    settings.postgres_user,
                    "--pwfile",
                    str(password_path),
                    "--auth=scram-sha-256",
                    "--encoding=UTF8",
                    "--locale=C",
                ]
            )
        finally:
            password_path.unlink(missing_ok=True)
    if run([str(pg_ctl), "-D", str(DATA), "status"], check=False).returncode != 0:
        run(
            [
                str(pg_ctl),
                "-D",
                str(DATA),
                "-l",
                str(ROOT / "tmp/postgres.log"),
                "-o",
                f"-h 127.0.0.1 -p {settings.postgres_port}",
                "-w",
                "start",
            ]
        )
    with psycopg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        dbname="postgres",
        user=settings.postgres_user,
        password=settings.postgres_password.get_secret_value(),
        autocommit=True,
        connect_timeout=5,
    ) as connection:
        exists = connection.execute(
            "SELECT 1 FROM pg_database WHERE datname=%s",
            (settings.postgres_db,),
        ).fetchone()
        if not exists:
            connection.execute(
                sql.SQL("CREATE DATABASE {}").format(sql.Identifier(settings.postgres_db))
            )
    print("Local PostgreSQL is ready. Run migrations and the synthetic seed next.")


if __name__ == "__main__":
    main()
