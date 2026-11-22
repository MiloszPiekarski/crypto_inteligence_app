# Kontekst projektu dla asystenta AI

GoatCash (goatcash.app): platforma analityczna rynku kryptowalut + bot, praca inżynierska
(Politechnika Krakowska) i darmowy produkt publiczny. Dokumentacja źródłowa: „Roadmapa i
dokumentacja techniczna platformy” (zakładki: Fundamenty i decyzje, Roadmapa E0–E17,
Testy i quality gates).

Zasady pracy:

- Działamy dokładnie według roadmapy: bez pomijania, bez podmieniania, bez udawania, że coś
  jest zrobione. Etap jest zaliczony dopiero, gdy jego bramka przejdzie z dowodem.
- Odstępstwo od dokumentacji = jawna decyzja zapisana w dokumentacji (nie po cichu).
- Sekrety nigdy w repo ani w czacie. `.env.local` lokalnie, SOPS + age dla środowisk.
- Python: pakiet `goatcash` (nazwa `platform` koliduje z modułem standardowym Pythona),
  moduły przez `goatcash.<moduł>.api`, implementacja w `_impl`, import-linter w CI.
- Właściciel pracuje na macOS (Apple Silicon); serwer docelowy: Oracle A1 (arm64), Amsterdam.
