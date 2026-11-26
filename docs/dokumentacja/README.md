# Dokumentacja projektu GoatCash

Trzy dokumenty źródłowe projektu (pracy inżynierskiej i produktu):

| Plik                             | Zawartość                                                                                   |
| -------------------------------- | ------------------------------------------------------------------------------------------- |
| [`fundamenty.md`](fundamenty.md) | Fundamenty i decyzje: stos, architektura, struktura repozytorium, bezpieczeństwo            |
| [`roadmapa.md`](roadmapa.md)     | Roadmapa etapów E0–E18: cel, zależności, zakres prac, testy; **stan realizacji z dowodami** |
| [`testy.md`](testy.md)           | Strategia testów i quality gates: bramki, ich status i dowody, pipeline CI/CD               |

## Źródło prawdy

Od 22.11.2026 źródłem prawdy są **te pliki w repozytorium** (decyzja właściciela). Zmieniają się
przez PR, więc każda zmiana ma historię, autora i przegląd. Wersja w Claude Docs („Roadmapa
i dokumentacja techniczna platformy”) to archiwum stanu z 22.11.2026 i nie jest dalej
aktualizowana.

## Oznaczenia stanu

- ✅ zrobione i sprawdzone; obok jest dowód (plik, przebieg CI, raport bramki),
- ⚠️ zrobione według właściciela, ale bez dowodu w repozytorium (do potwierdzenia),
- ⏳ w toku,
- ⬜ nie rozpoczęto,
- ⏸ odłożone do ścieżki produktu (realizacja po obronie pracy, ADR-0008).

## Dwie ścieżki (od 26.11.2026)

Teraz realizujemy **ścieżkę pracy inżynierskiej**: zakres pracy i tabele w
[`fundamenty.md`, sekcja 0](fundamenty.md#0-zakres-pracy-inżynierskiej), kolejność etapów
w tabeli „Kolejność prac” na początku [`roadmapa.md`](roadmapa.md), bramki pracy `G<nr>p`
w [`testy.md`, sekcja 3a](testy.md). Pełny produkt (karty etapów, pełne bramki) zostaje
opisany obok i wraca po obronie. Mapa rozdziałów pracy: [`../praca/README.md`](../praca/README.md).

Etap jest zaliczony dopiero wtedy, gdy jego bramka (w ścieżce pracy: bramka pracy `G<nr>p`) ma plik `docs/gates/G<nr>.passed.json` (albo `G<nr>p.passed.json`),
który sprawdza `gate-guard`. Bieżący stan pracy i następne kroki: [`../stan-pracy.md`](../stan-pracy.md).
