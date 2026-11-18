"""Launch a NEW isolated PostgreSQL synthetic sandbox. Never migrates the active DB."""

import argparse
import json
import re
import socket
from uuid import uuid4

import psycopg
import uvicorn
from alembic import command
from alembic.config import Config
from psycopg import sql
from sqlalchemy.orm import Session

from app.core.config import ROOT, Settings
from app.db.session import create_db_engine
from app.main import create_app
from app.repositories.intelligence import IntelligenceRepository
from scripts.seed_demo_data import seed_demo
from scripts.synthetic_scenarios import create_scenarios


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume the recorded sandbox without seeding or migrating",
    )
    args = parser.parse_args()
    original = Settings()
    if original.postgres_host not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("Only local development PostgreSQL is supported")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", args.port))
    output = ROOT / "tmp/investigation-sandbox.json"
    previous = json.loads(output.read_text()) if args.resume else None
    database = previous["database"] if previous else "fraudsentinel_sandbox_" + uuid4().hex[:16]
    if not re.fullmatch(r"fraudsentinel_sandbox_[a-f0-9]{16}", database):
        raise RuntimeError("Recorded database is not an isolated synthetic sandbox")
    assert database != original.postgres_db
    if not args.resume:
        with psycopg.connect(
            host=original.postgres_host,
            port=original.postgres_port,
            dbname="postgres",
            user=original.postgres_user,
            password=original.postgres_password.get_secret_value(),
            autocommit=True,
        ) as connection:
            connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    settings = Settings(
        _env_file=None,
        app_env="development",
        demo_mode=True,
        investigation_sandbox=True,
        postgres_host=original.postgres_host,
        postgres_port=original.postgres_port,
        postgres_user=original.postgres_user,
        postgres_password=original.postgres_password,
        postgres_db=database,
        scoring_rules_path=original.scoring_rules_path,
        cors_origins=["http://127.0.0.1:5175", "http://localhost:5175"],
    )
    engine = create_db_engine(settings)
    config = Config(str(ROOT / "backend/alembic.ini"))
    with engine.begin() as connection:
        assert connection.engine.url.database == database
        config.attributes["connection"] = connection
        if not args.resume:
            command.upgrade(config, "head")
        command.check(config)
    if not args.resume:
        with Session(engine) as session, session.begin():
            seed_demo(session)
            scenarios = create_scenarios(IntelligenceRepository(session, "user_demo_analyst"))
    else:
        scenarios = previous["scenarios"]
    output.parent.mkdir(exist_ok=True)
    output.write_text(
        json.dumps({"database": database, "port": args.port, "scenarios": scenarios}, indent=2)
    )
    print(f"Synthetic sandbox ready: {database}; active development database unchanged.")
    uvicorn.run(create_app(settings, engine), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
