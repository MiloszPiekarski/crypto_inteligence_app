"""Wersja pakietu odczytywana z metadanych instalacji."""

from importlib.metadata import PackageNotFoundError, version


def package_version(distribution: str = "goatcash-platform") -> str:
    """Zwraca wersję zainstalowanej dystrybucji albo jawne "unknown" (bez cichego fallbacku)."""
    try:
        return version(distribution)
    except PackageNotFoundError:
        return "unknown"
