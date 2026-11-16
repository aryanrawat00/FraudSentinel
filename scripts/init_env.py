"""Create local configuration without printing or overwriting secrets."""

import argparse
import secrets
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--postgres-port", type=int, default=5432)
    args = parser.parse_args()
    if not 1 <= args.postgres_port <= 65535:
        parser.error("PostgreSQL port must be between 1 and 65535")
    root = Path(__file__).resolve().parents[1]
    target = root / ".env"
    if target.exists():
        print("Existing .env preserved. Edit it locally if settings need to change.")
        return
    template = (root / ".env.example").read_text(encoding="utf-8")
    content = template.replace(
        "POSTGRES_PASSWORD=\n", f"POSTGRES_PASSWORD={secrets.token_urlsafe(32)}\n"
    )
    content = content.replace("POSTGRES_PORT=5432", f"POSTGRES_PORT={args.postgres_port}")
    with target.open("x", encoding="utf-8", newline="\n") as output:
        output.write(content)
    print("Created ignored .env with a random local database password. No secret was printed.")


if __name__ == "__main__":
    main()
