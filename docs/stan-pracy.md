# Stan pracy (aktualizowany po każdym kroku)

Ten plik pozwala wznowić pracę w nowej rozmowie z asystentem AI bez utraty kontekstu:
na początku rozmowy wystarczy poprosić o przeczytanie `CLAUDE.md` i tego pliku.

**Ostatnia aktualizacja:** 2026-11-22

## Gdzie jesteśmy

- **E0:** zakończony, G0 zaliczona (dowód lokalny).
- **E1:** zakończony, G1 zaliczona (CI na `main`, przebieg 45027155138; `make gate G=1` u właściciela 17/17).
- **Teraz:** domknięcie E1 przed E2:
  1. PR „domknięcie E1”: dokumentacja w repo, `G0/G1.passed.json`, ADR-001 zatwierdzony, reguły Dependabota, skrypty `gate_pass.py` i `gate_guard.py`.
  2. PR „gate-guard”: workflow `gate-guard.yml`, potem `./scripts/github-setup.sh` (wymagany check `gate-guard`).
- **Następnie:** E2 (architektura szczegółowa, model danych, kontrakty), w kilku mniejszych PR.

## Otwarte sprawy

- `doctor.sh` (naprawione w domknięciu E1): w katalogu projektu `uv python find 3.12` zwraca
  ścieżkę `.venv` bez numeru wersji, więc test „Python (uv)” dawał FAIL; raport bramki
  zapisuje teraz wszystkie wiersze z FAIL, nie tylko 25 ostatnich linii.

- ⚠️ E0: potwierdzić włączenie Cloudflare R2, konto Resend i bota Telegram (brak dowodu w repo).
- Sentry na koncie prywatnym: przepiąć na konto projektu w E3/E6.
- PR-y Dependabota sprzed nowych reguł (Python 3.15, TypeScript 7, @types/node 26): zamknąć bez scalania.
- Opcjonalnie: usunąć stary ruleset „Protect main” (zastąpiony przez `main-protection`).
- Nowy klucz Anthropic przed 19.02.2027.

## Jak pracujemy (skrót, pełne zasady w `CONTRIBUTING.md`)

- Asystent przygotowuje zmiany jako łatki (`git apply`), wcześniej testuje je na gałęzi
  `claude/…` w szkicu PR (CI na Linuksie i macOS), właściciel nakłada, commituje (podpis SSH) i scala.
- Niezależny recenzent (osobny agent) tylko wtedy, gdy zmiana tego wymaga (sekrety,
  bezpieczeństwo) i po zgodzie właściciela: jest drogi i trwa długo.
- Uwagi Graphify i Copilota: triaż według tabeli w `CONTRIBUTING.md`.
