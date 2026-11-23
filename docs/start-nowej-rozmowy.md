# Start nowej rozmowy z asystentem (każdy etap w nowej rozmowie)

Wklej poniższy tekst na początku rozmowy, zmieniając numer etapu. Zasady pracy są w
`CLAUDE.md` (sekcja „Zasady współpracy”), stan i otwarte sprawy w `docs/stan-pracy.md`;
ten plik ich nie powtarza.

```text
Kontynuujemy projekt GoatCash. Zaczynamy etap E<nr>. Odpowiadaj po polsku.

1. Podłącz repozytorium MiloszPiekarski/crypto_inteligence_app z prawem zapisu (add_repo,
   access: push) i sklonuj je.
2. Przeczytaj: CLAUDE.md, docs/stan-pracy.md, docs/lekcje.md, CONTRIBUTING.md,
   docs/dokumentacja/README.md, całą sekcję E<nr> w docs/dokumentacja/roadmapa.md,
   docs/dokumentacja/testy.md (sekcja 3 i „Wdrożenie w repozytorium”), raport poprzedniej
   bramki docs/gates/G<nr-1>.md, wymagania z `gate: G<nr>` w docs/wymagania.yaml
   i docs/start-nowej-rozmowy.md (ograniczenia sesji).
3. Sprawdź stan na GitHubie przez REST (gh api): ostatnie przebiegi ci.yml na main,
   otwarte PR-y i zgłoszenia, rulesety.
4. Napisz mi krótko (5–8 punktów), gdzie jesteśmy i co jest otwarte. Jeśli coś w repo
   nie zgadza się z dokumentacją, powiedz to wprost.
5. Zaproponuj podział E<nr> na małe PR-y (jedna rzecz na PR) z planem bramki G<nr>
   i zapytaj o akceptację. Dopiero potem zaczynamy.
```

## Ograniczenia sesji asystenta (stan po E2, 23.11.2026)

- GraphQL GitHuba niedostępny: tylko `gh api` (REST). API ustawień Actions i pobieranie
  artefaktów przebiegów są zablokowane przez proxy sesji (ustawienia sprawdza właściciel).
- Usuwanie gałęzi `claude/…` przez asystenta kończy się 403: usuwa je właściciel
  (`git push origin --delete …`).
- Docker Hub jest niedostępny z sesji: testy z obrazem bazy (TimescaleDB) przechodzą
  dopiero w CI na ubuntu i u właściciela; lokalnie asystent sprawdza SQL na Postgresie 16
  bez Timescale.
- GitHub (poza podłączonym repo) jest niedostępny z powłoki sesji: wersje akcji i narzędzi
  sprawdzać przez dokumentację i CI.
- Szkic PR testowy musi mieć bazę na aktualnym `main` (gałąź oparta na niescalonym commicie
  daje konflikt i CI się nie uruchamia).
- Biome formatuje Markdown (tabele, `__tekst__` → `**tekst**`): skrypty zmieniające pliki
  sprawdzają każdą zamianę (`assert`), a znaczników nie zapisuje się podkreśleniami.
- `gh pr create` i `--label` używają GraphQL: szkic PR przez `gh api …/pulls -F draft=true`,
  etykieta przez `gh api …/issues/<nr>/labels`, zamknięcie szkicu przez `PATCH state=closed`.
- `make audit` w sesji: zizmor dostaje 401, gdy w środowisku jest token sesji; uruchamiać
  `GH_TOKEN= GITHUB_TOKEN= make audit` (w CI i u właściciela bez zmian).
- `make gate G=1` w sesji ma 2 oczekiwane FAIL: sondy SOPS (brak klucza age właściciela)
  i statyczna kontrola (jak wyżej). Pełny wynik daje CI i właściciel.
- Ruleset wymaga gałęzi aktualnej względem `main`: po scaleniu innego PR właściciel robi
  `gh pr update-branch <nr>` i czeka na nowe CI.
- Chmura (od E3): asystent nie dostaje kluczy Oracle ani Cloudflare. Komendy z tymi
  kluczami uruchamia właściciel (według instrukcji) albo CI (sekrety w SOPS i GitHub);
  asystent sprawdza wklejone wyniki, które nie zawierają wartości sekretów.
