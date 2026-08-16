from __future__ import annotations

import argparse
import asyncio

from app.security import encode_secret_for_env


def main() -> None:
    parser = argparse.ArgumentParser(description="Token Station maintenance utilities")
    parser.add_argument("command", choices=["generate-encryption-key", "retention"])
    args = parser.parse_args()
    if args.command == "generate-encryption-key":
        print(encode_secret_for_env())
    elif args.command == "retention":
        from app.maintenance import run_retention

        result = asyncio.run(run_retention())
        print(
            "Retention complete: "
            f"archived={result['request_logs_archived']} "
            f"expired_aggregates={result['old_aggregates_deleted']}"
        )


if __name__ == "__main__":
    main()
