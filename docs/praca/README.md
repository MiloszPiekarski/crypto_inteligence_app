# Praca inżynierska: mapa „rozdział → dokumenty i dowody w repo”

Temat: **Aplikacja webowa do analizy rynku kryptowalut z wykorzystaniem systemu
wieloagentowego** (EN: _A web application for cryptocurrency market analysis using
a multi-agent system_). Zakres pracy dosłownie i tabela „wymóg → etap → dowód”:
[`fundamenty.md`, sekcja 0](../dokumentacja/fundamenty.md#0-zakres-pracy-inżynierskiej).
Decyzja o dwóch ścieżkach: [ADR-0008](../adr/0008-dwie-sciezki.md).

Ten plik pokazuje, skąd brać treść i dowody do każdego rozdziału. Kolumna „Stan” jest
aktualizowana przy domknięciu etapu (✅ tylko z dowodem, ⏳ w toku, ⬜ nie rozpoczęto).

| Rozdział pracy (propozycja)                    | Dokumenty w repo                                                                                                                                               | Dowody                                                             | Stan |
| ---------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ | ---- |
| 1. Wstęp, cel i zakres                         | `fundamenty.md` sekcja 0; `roadmapa.md` „Kolejność prac”                                                                                                       | –                                                                  | ✅   |
| 2. Analiza dziedziny i rozwiązań istniejących  | `fundamenty.md` sekcje 1–3 (decyzje, dane rynkowe, dostawcy)                                                                                                   | –                                                                  | ⏳   |
| 3. Wymagania funkcjonalne i niefunkcjonalne    | `docs/wymagania.yaml` (pole `track: praca`), roadmapa E2 „Wymagania niefunkcjonalne”                                                                           | `make requirements-check` (bramka G2)                              | ✅   |
| 4. Architektura aplikacji                      | `fundamenty.md` sekcja 2; `docs/architektura/c4.md`; `docs/architektura/stride.md`; ADR-0001…0008                                                              | G2, G3 (`docs/gates/G2.md`, `G3.md`)                               | ✅   |
| 5. Model danych                                | roadmapa E2 „Model danych”; ADR-0002; migracje `services/platform/src/goatcash/migrations`; kontrakty `packages/contracts` (zdarzenia, `Evidence` v1, OpenAPI) | G2 (migracja w obie strony, schematy)                              | ✅   |
| 6. Infrastruktura i wdrożenie                  | ADR-0007; `infra/`; runbooki `docs/runbooks/`                                                                                                                  | G3 (odtworzenie < 30 min, kopie, alerty)                           | ✅   |
| 7. Pozyskiwanie i jakość danych                | roadmapa E4 (ścieżka pracy); moduł `marketdata`                                                                                                                | G4p (`docs/gates/G4p.md`): DQ, raport luk i kompletności           | ✅   |
| 8. Metody analizy danych                       | [`metody.md`](metody.md) (wskaźniki, agenci, HMM, GARCH, kNN, LightGBM, fuzja, ocena ryzyka, metryki)                                                          | G5p, G7p, G8p, G9p                                                 | ⬜   |
| 9. System wieloagentowy                        | roadmapa E7 i E9 (ścieżka pracy); moduły `agents`, `ledger`, `fusion`                                                                                          | G7p (agenci, Ledger), G9p (fuzja, ryzyko, podpowiedzi)             | ⬜   |
| 10. Modele uczenia maszynowego i ich ocena     | roadmapa E8 (ścieżka pracy); moduł `ml`; raport walk-forward w `docs/praca/`                                                                                   | G8p (odtwarzalność, brak wycieku, raport)                          | ⬜   |
| 11. Moduł testowania strategii                 | roadmapa E11 (ścieżka pracy); moduł `backtest`                                                                                                                 | G11p (zgodność z ręcznym przeliczeniem, pułapka)                   | ⬜   |
| 12. Projekt graficznego interfejsu użytkownika | roadmapa E12a; makiety i design system w `docs/praca/gui/`                                                                                                     | G12p (makiety w repo)                                              | ⬜   |
| 13. Implementacja prototypu                    | `services/platform`, `apps/web`; `CONTRIBUTING.md`; CI `.github/workflows/ci.yml`                                                                              | przebiegi CI na `main`, wdrożenie `app.goatcash.app`               | ⬜   |
| 14. Testy: poprawność modułów analitycznych    | `testy.md` (sekcje 1, 2 i 3a); testy w `services/platform/tests`                                                                                               | raporty bramek pracy `docs/gates/G<nr>p.md` i `G<nr>p.passed.json` | ⬜   |
| 15. Testy: prezentacja wyników użytkownikowi   | `testy.md` sekcja 3a (G12p); raport `docs/praca/test-uzytkownikow.md` (3 osoby, 4 zadania, SUS)                                                                | G12p (Playwright, axe, informacja o braku porady)                  | ⬜   |
| 16. Podsumowanie, ograniczenia i dalszy rozwój | ADR-0008 (co przechodzi do produktu); podsekcje „Dokończenie w ścieżce produktu” w roadmapie                                                                   | –                                                                  | ⬜   |

## Pliki tego katalogu

- [`metody.md`](metody.md): opis zastosowanych metod analizy danych; uzupełniany przy
  domknięciu E5, E7, E8, E9 i E11 (wzory, założenia, ograniczenia, wyniki z raportów bramek).
- `gui/` (od E12a): eksport makiet z Figma Free (PNG albo PDF), persony, zadania kluczowe,
  mini design system.
- `test-uzytkownikow.md` (E12b): scenariusz, wyniki 3 osób, kwestionariusz SUS i wnioski.
- Raporty walk-forward (E7, E8, E9): wyniki względem punktów odniesienia, opisane uczciwie,
  także gdy model nie ma przewagi.
