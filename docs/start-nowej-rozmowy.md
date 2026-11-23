# Start nowej rozmowy z asystentem (każdy etap w nowej rozmowie)

Wklej poniższy tekst na początku rozmowy, zmieniając numer etapu. Zasady pracy są w
`CLAUDE.md` (sekcja „Zasady współpracy”), stan i otwarte sprawy w `docs/stan-pracy.md`;
ten plik ich nie powtarza.

```text
Kontynuujemy projekt GoatCash. Zaczynamy etap E<nr>. Odpowiadaj po polsku.

1. Tryb lokalny (domyślny od 23.11.2026): Claude Code na moim Macu w katalogu
   ~/Documents/Millosz/crypto_app. Sprawdź, że działają blokady z sekcji „Blokady sesji
   lokalnej” w docs/start-nowej-rozmowy.md, i pracuj w git worktree na gałęziach claude/….
   (Sesja w chmurze: podłącz repo MiloszPiekarski/crypto_inteligence_app przez add_repo
   z access: push i sklonuj je; obowiązuje wtedy tryb łatek.)
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

## Blokady sesji lokalnej (od 23.11.2026)

W trybie lokalnym asystent działa na komputerze właściciela, z jego `gh` i dostępem do jego
plików. Obietnica „nie zaglądam do kluczy” nie wystarcza, więc w ustawieniach Claude Code
**poza repo** (`~/.claude/settings.json`, obowiązują we wszystkich projektach na tym Macu)
są dwie warstwy blokad. Zmienia je tylko właściciel: oba pliki są objęte regułą `deny`
dla narzędzi edycji, a hook odrzuca komendy, które ich dotyczą.

1. **Reguły `permissions.deny`** (narzędzia Read, Edit/Write, Grep): `Read` i `Edit` dla
   `//**/.env.local`, `~/.oci/**`, `~/.ssh/**`, `~/.config/sops/age/**`
   (`Read` także `~/Library/Application Support/sops/age/**`); `Edit` dla
   `~/.claude/settings.json` i `~/.claude/hooks/**`; `Bash` dla `gh pr merge *`,
   `terraform apply *`, `terraform destroy *` (i tak samo `tofu`).
2. **Hook `PreToolUse`** `~/.claude/hooks/goatcash-guard.py`: sprawdza całą treść każdej
   komendy Bash (także wewnątrz `sh -c`, `$(…)` i łańcuchów `&&`). Blokuje wzmianki
   o ścieżkach z sekretami (`.env.local`, `.oci`, `.ssh`, `sops/age`, `keys.txt`, klucz
   podpisu) i `gh auth token`; `terraform|tofu … apply|destroy` (także z `-chdir=`);
   `gh pr merge`; `gh api` do scalania, refów, treści repo, rulesetów, środowisk i sekretów;
   `git push` na cokolwiek poza `claude/…` (także `--all`, `--mirror`, `--tags` i push
   bez jawnej gałęzi); komendy dotyczące ustawień i hooków Claude Code. Błąd hooka blokuje
   komendę.

Próba z 23.11.2026 (rozmowa E3): Read `.env.local`, `~/.ssh`, `~/.oci`,
`~/.config/sops/age` i Write wabika `.env.local` → odmowa; `gh pr merge`,
`terraform -chdir=… apply`, `git push origin HEAD:main`, `sh -c 'cat ~/.oci/…'`,
Edit `settings.json` → odmowa; `git push --dry-run origin HEAD:claude/…` → dozwolone.
Hook ma też test 27 przypadków (18 blokowanych, 9 dozwolonych).

**Czego te blokady nie łapią (to nie jest izolacja):**

- komendy zaciemnionej: ścieżki sklejanej w Pythonie albo Node (`chr(46)+'ssh'`), zmiennych,
  base64. Próba z 23.11.2026: `python3 -c` sklejający `~/.ssh/__probe__` dotarł do systemu
  plików (zatrzymał go tylko brak pliku);
- skryptu z pliku (`./x.sh`, cel `make`, test pytest), który sam czyta sekrety, robi `push`
  albo `terraform apply`: hook widzi tylko tekst komendy, nie to, co ona uruchamia;
- aliasów git (`git p`) i `git config` zmieniającego remote albo `pushurl`;
- tego, że `gh` i `git push` działają z kontem właściciela: GitHub nie odróżnia asystenta
  od właściciela; `main` chroni ruleset, pozostałe gałęzie właściciela tylko hook;
- sekretów, które już są w zmiennych środowiska procesu;
- trybu `bypassPermissions` i zmian ustawień przez samego właściciela.

Hook daje też fałszywe alarmy (w bezpieczną stronę): blokuje każdą komendę, której tekst
zawiera np. `.env.local`, a `2>&1` po `git push` bierze za nazwę gałęzi.

Mocniejsza warstwa (do decyzji właściciela): sandbox Claude Code (`sandbox.enabled`,
`sandbox.filesystem.denyRead`, `allowUnsandboxedCommands: false`) blokuje odczyt na poziomie
systemu dla komend Bash. Domyślnie odcina jednak sieć (lista domen), działa we wszystkich
projektach i wymaga wyjątków dla `gh` i `git push` przez SSH. Pełna izolacja to osobny
użytkownik macOS albo maszyna wirtualna.

## Ograniczenia sesji asystenta w chmurze (stan po E2, 23.11.2026)

Dotyczą sesji w chmurze (tryb łatek); w trybie lokalnym większość z nich nie występuje.

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
