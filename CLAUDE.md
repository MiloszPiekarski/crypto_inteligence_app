# Kontekst projektu dla asystenta AI

GoatCash (goatcash.app): platforma analityczna rynku kryptowalut + bot, praca inżynierska
(Politechnika Krakowska) i darmowy produkt publiczny. Dokumentacja źródłowa jest w repo:
`docs/dokumentacja/` (fundamenty.md, roadmapa.md, testy.md; od 22.11.2026 źródło prawdy,
wersja w Claude Docs to archiwum). **Na początku każdej rozmowy przeczytaj
`docs/stan-pracy.md`** (gdzie jesteśmy, otwarte sprawy) i aktualizuj go po każdym kroku.

Zasady pracy:

- Działamy dokładnie według roadmapy: bez pomijania, bez podmieniania, bez udawania, że coś
  jest zrobione. Etap jest zaliczony dopiero, gdy jego bramka przejdzie z dowodem.
- Odstępstwo od dokumentacji = jawna decyzja zapisana w dokumentacji (nie po cichu).
- Sekrety nigdy w repo ani w czacie. `.env.local` lokalnie, SOPS + age dla środowisk.
- Python: pakiet `goatcash` (nazwa `platform` koliduje z modułem standardowym Pythona),
  moduły przez `goatcash.<moduł>.api`, implementacja w `_impl`, import-linter w CI.
- Właściciel pracuje na macOS (Apple Silicon); serwer docelowy: Oracle A1 (arm64), Amsterdam.
- Stan realizacji w `docs/dokumentacja/roadmapa.md` i `testy.md` oznaczamy na bieżąco
  (✅ tylko z dowodem: plik, przebieg CI, raport bramki; ⚠️ gdy dowodu brak).
- Zmiany przygotowuje asystent jako łatki, przetestowane wcześniej na gałęzi `claude/…`
  w szkicu PR (CI na Linuksie i macOS). Przed wysłaniem: `make gate`, `CI=true make gate`,
  `make audit` i pytanie „jak obejść tę kontrolę?”. Niezależny recenzent (osobny agent)
  tylko przy zmianach bezpieczeństwa i za zgodą właściciela.
