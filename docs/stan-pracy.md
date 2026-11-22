# Stan pracy (aktualizowany po każdym kroku)

Ten plik pozwala wznowić pracę w nowej rozmowie z asystentem AI bez utraty kontekstu:
na początku rozmowy wystarczy poprosić o przeczytanie `CLAUDE.md` i tego pliku.

**Ostatnia aktualizacja:** 2026-11-22

## Gdzie jesteśmy

- **E0:** zakończony, G0 zaliczona (`docs/gates/G0.passed.json`, dowód lokalny).
- **E1:** zakończony i domknięty, G1 zaliczona (`docs/gates/G1.passed.json`, przebieg 45027155138).
  - PR #1 (E1), #12 (dokumentacja w repo, dowody bramek), #13 (`gate-guard`) scalone.
  - Wymagane checki `main`: `ci-ok` i `gate-guard`.
- **Zasady współpracy z asystentem** zapisane w `CLAUDE.md` (PR z etykietą `E2`).
- **Następny etap: E2** (architektura szczegółowa, model danych, kontrakty; wymaga G1).
  Zaczynamy w nowej rozmowie, od zakresu E2 w `docs/dokumentacja/roadmapa.md`,
  w kilku mniejszych PR z etykietą `E2`.

## Otwarte sprawy

- ⚠️ E0: potwierdzić włączenie Cloudflare R2, konto Resend i bota Telegram (brak dowodu w repo).
- Sentry na koncie prywatnym: przepiąć na konto projektu w E3/E6.
- Opcjonalnie: usunąć stary ruleset „Protect main” (zastąpiony przez `main-protection`).
- Nowy klucz Anthropic przed 19.02.2027.
- Graphify przy PR #12 zgłosił 18 „możliwych problemów”; przejrzane tylko 3 widoczne
  (panel Graphify jest dla właściciela niedostępny).
- Atrybucja „Data by CoinGecko” w interfejsie: w E12.
- Niespójności w dokumentacji do poprawy osobnym PR: nagłówek `docs/gates/G1.md` nadal
  „W TOKU” (G1 jest zaliczona), tytuł `roadmapa.md` „E0–E17”, choć jest karta E18.

## Jak pracujemy (skrót; pełne zasady: `CLAUDE.md`, sekcja „Zasady współpracy”, i `CONTRIBUTING.md`)

- Asystent przygotowuje zmiany jako łatki (`git apply`), wcześniej testuje je na gałęzi
  `claude/…` w szkicu PR (CI na Linuksie i macOS); właściciel nakłada, commituje (podpis SSH),
  otwiera PR z etykietą etapu i scala.
- Niezależny recenzent (osobny agent) tylko wtedy, gdy zmiana tego wymaga (sekrety,
  bezpieczeństwo) i po zgodzie właściciela: jest drogi i trwa długo.
- Uwagi Graphify i Copilota: asystent robi triaż (naprawiamy / odpowiadamy / ignorujemy)
  i daje gotowe odpowiedzi; kod zmieniamy tylko przy problemach bezpieczeństwa,
  poprawności albo bramki.
- PR-y Dependabota mają etykietę `dependencies` (gate-guard je przepuszcza); duże wersje
  są wyłączone regułami w `.github/dependabot.yml`.
