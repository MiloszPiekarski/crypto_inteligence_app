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
  W toku według planu niżej (zaakceptowany przez właściciela 22.11.2026).

## Plan E2 (PR-y z etykietą `E2`, jedna rzecz na PR)

| #   | Gałąź                      | Zakres                                                                                       | Stan |
| --- | -------------------------- | -------------------------------------------------------------------------------------------- | ---- |
| 0   | `docs/E2-spojnosc-g1`      | nagłówek `G1.md` (zaliczona), tytuł roadmapy E0–E18, ten plan (PR #18)                       | ✅   |
| 0a  | `ci/E2-gate-guard-wyscig`  | `gate-guard`: etykiety z API, bez `opened` i bez anulowania przebiegów (PR #20)              | ✅   |
| 1   | `ci/E2-bramka-g2`          | `gates/G2.yaml` + szkic `docs/gates/G2.md`; bramka czerwona, dopóki nie ma treści            | ⏳   |
| 2   | `docs/E2-adr`              | ADR-002 model danych, 003 Valkey Streams, 004 uwierzytelnianie, 005 bramka LLM, 006 executor | ⬜   |
| 3   | `feat/E2-migracja-0001`    | Alembic, migracja 0001, test `upgrade head` / `downgrade base` (testcontainers)              | ⬜   |
| 4   | `feat/E2-schematy-zdarzen` | JSON Schema 8 zdarzeń z `schema_version`, testy poprawnych i błędnych przykładów             | ⬜   |
| 5   | `feat/E2-evidence-v1`      | kontrakt `Evidence` v1 + testy                                                               | ⬜   |
| 6   | `feat/E2-openapi`          | szkic OpenAPI 3.1 z FastAPI `/v1`, Spectral w CI, klient TS w `packages/contracts`           | ⬜   |
| 7   | `docs/E2-wymagania`        | F-xx i NF-xx w `docs/wymagania.yaml` + skrypt kompletności                                   | ⬜   |
| 8   | `docs/E2-stride`           | model zagrożeń STRIDE: API, executor, panel administratora                                   | ⬜   |
| 9   | `docs/E2-c4`               | diagram C4 (kontekst, kontenery) w Mermaid                                                   | ⬜   |
| 10a | `ci/E2-gate-guard-target`  | luka: PR może podmienić `gate-guard.yml`; naprawa przed zaliczeniem G2                       | ⬜   |
| 10  | `docs/E2-g2`               | bramka na `main`, raport `G2.md`, `G2.passed.json`                                           | ⬜   |

Decyzje właściciela do planu (22.11.2026):

- Wymagania w `docs/wymagania.yaml` (sprawdzane skryptem), C4 w Mermaid.
- Test migracji (testcontainers) tylko na ubuntu: runnery macOS w GitHub Actions nie mają
  Dockera. Na macOS bramka G2 sprawdza schematy, Spectral i wymagania. Jawne odstępstwo,
  zapisane w `docs/gates/G2.md`.
- Tabele Better Auth tworzy nasza migracja Alembic (jedno źródło schematu). ADR-004 musi
  opisać wykrywanie rozjazdu po aktualizacji Better Auth: CI porównuje schemat wymagany przez
  przypiętą wersję Better Auth (jego CLI) ze schematem z migracji; różnica = czerwone CI.

## Otwarte sprawy

- ⚠️ E0: R2, Resend i bot Telegram założone (według właściciela, 22.11.2026), w repo brak
  dowodu, w `.env.local` brak kluczy. Decyzja: R2 i Telegram dostają sprawdzenie w `doctor.sh`
  (osobny PR E0, klucze tylko do odczytu w `.env.local`); Resend ma na razie tylko konto,
  domena `goatcash.app` w Resend, klucz API i sprawdzenie dochodzą w E13 (do tego czasu ⚠️).
- Sentry na koncie prywatnym: przepiąć na konto projektu w E3/E6.
- Opcjonalnie: usunąć stary ruleset „Protect main” (zastąpiony przez `main-protection`).
- Nowy klucz Anthropic przed 19.02.2027.
- Graphify przy PR #12 zgłosił 18 „możliwych problemów”; przejrzane tylko 3 widoczne
  (panel Graphify jest dla właściciela niedostępny).
- Atrybucja „Data by CoinGecko” w interfejsie: w E12.
- Bramka G2 działa w CI jako job „8 bramka G2” poza `ci-ok` (czerwona do końca E2); każdy PR
  z elementem E2 dodaje swój cel Makefile z `gates/G2.yaml`.
- ⚠️ Luka w `gate-guard` (istniejąca od #13): przy zdarzeniu `pull_request` GitHub używa pliku
  workflow z PR, więc PR zmieniający `.github/workflows/gate-guard.yml` może sam ominąć kontrolę
  (skrypt jest brany z `main`, ale komenda w workflow już nie). Decyzja (właściciel zostawił wybór asystentowi): naprawa
  PR-em 10a przed zaliczeniem G2, bez osobnego recenzenta (wariant: `pull_request_target`
  bez kodu z PR).

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
