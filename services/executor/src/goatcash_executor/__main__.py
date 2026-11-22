"""Punkt wejścia `python -m goatcash_executor`: wypisuje wersję."""

from goatcash.common.api import package_version


def main() -> int:
    print(f"goatcash-executor {package_version('goatcash-executor')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
