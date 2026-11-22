"""Sonda bramki G1: celowo zakazany import. Ten PR nie może zostać scalony."""

import goatcash.ledger._impl as ledger_impl


def probe() -> str | None:
    return ledger_impl.__doc__
