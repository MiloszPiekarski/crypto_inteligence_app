"""Punkt wejścia `python -m goatcash`: wypisuje wersję (używany w obrazie Dockera)."""

from goatcash.common.api import package_version


def main() -> int:
    print(f"goatcash-platform {package_version()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
