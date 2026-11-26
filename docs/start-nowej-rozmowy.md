# Start nowej rozmowy z asystentem (każdy etap w nowej rozmowie)

Zasady pracy są w `CLAUDE.md`, stan i otwarte sprawy w `docs/stan-pracy.md`; ten plik ich
nie powtarza. **Teraz obowiązuje ścieżka pracy inżynierskiej** (ADR-0008): używaj promptu
z sekcji „Ścieżka pracy”. Prompt z sekcji „Ścieżka produktu” wraca po przełączeniu
(sekcja „Przełączenie na ścieżkę produktu”).

## Ścieżka pracy (teraz): krótki prompt na etap

Kolejność etapów: E4 → E5 → E6 → E12a → E7 → E8 → E9 → E11 → E12b (tabela „Kolejność prac”
w `docs/dokumentacja/roadmapa.md`). Rozmowa działa jako sesja w chmurze z repozytorium,
bez dostępu do Maca właściciela, w trybie z `CLAUDE.md`, sekcja „Tryb ścieżki pracy”.
Wklej poniższy tekst, zamieniając `E<nr>` na etap (np. `E5`) i `G<nr>p` na jego bramkę pracy
(np. `G5p`; dla E12a i E12b: `G12p`).

```text
GoatCash: etap E<nr> w ścieżce pracy inżynierskiej, bramka G<nr>p. Odpowiadaj po polsku.
Sesja w chmurze: repo MiloszPiekarski/crypto_inteligence_app (dostęp push); pracujesz
w trybie z CLAUDE.md, sekcja „Tryb ścieżki pracy”: sam piszesz kod i testy, otwierasz PR
z gałęzi claude/E<nr>-… z etykietą E<nr> i poprawiasz go do zielonego CI; ja scalam.

1. Przeczytaj: CLAUDE.md, docs/stan-pracy.md, docs/start-nowej-rozmowy.md (sekcje
   „Ścieżka pracy” i „Ograniczenia sesji asystenta w chmurze”), docs/lekcje.md, kartę E<nr>
   w docs/dokumentacja/roadmapa.md (najpierw podsekcja „Ścieżka pracy inżynierskiej”),
   bramkę G<nr>p w docs/dokumentacja/testy.md (sekcja 3a) i wymagania z work_gate: G<nr>p
   w docs/wymagania.yaml.
2. Sprawdź przez gh api (REST): ostatni przebieg ci.yml na main, otwarte PR-y, czy bramki
   wymagane dla E<nr> (gates/requirements.yaml, mapa „praca”) mają dowód na main.
3. Potwierdź w 5–8 punktach, co zrozumiałeś: zakres w ścieżce pracy, czego nie robimy
   (produkt), kryteria G<nr>p, testy obowiązkowe, sposób pracy. Niezgodności repo
   z dokumentacją napisz wprost.
4. Zaproponuj podział E<nr> na 1–3 PR-y (zawartość, testy, gdzie powstaje dowód G<nr>p)
   i czekaj na moją akceptację. Dopiero potem zaczynasz.
```

Domknięcie etapu w ścieżce pracy (ostatni PR etapu, potem mały PR z dowodem):

1. Job bramki `G<nr>p` przeniesiony z `gate-next` do macierzy `gate` w `ci.yml` (wartość
   macierzy `<nr>p`), raport `docs/gates/G<nr>p.md` z kryteriami i dowodami.
2. Po scaleniu i zielonym CI na `main`: `scripts/gate_pass.py` tworzy
   `docs/gates/G<nr>p.passed.json` (typ ci albo mixed, gdy bramka ma dowody ze staging);
   statusy ✅ w `roadmapa.md` (tabela „Kolejność prac”, status karty) i `testy.md`
   (sekcja 3a), `docs/stan-pracy.md`, `docs/praca/README.md` i `metody.md`, README
   (status), `docs/lekcje.md`.

## Przełączenie na ścieżkę produktu (po obronie)

1. **Decyzja właściciela** zapisana w nowym ADR (zastępuje punkt 1 ADR-0008 „ścieżka
   bieżąca”).
2. **Przełącznik:** PR właściciela zmieniający w `gates/requirements.yaml`
   `sciezka: praca` na `sciezka: produkt`. Od tej chwili `gate-guard` wymaga pełnych bramek
   (mapa `produkt`), a etapy odłożone przestają być odrzucane.
3. **Kolejność:** etapy w kolejności roadmapy; dla etapu ze ścieżki pracy realizujemy jego
   podsekcję „Dokończenie w ścieżce produktu” i pełną bramkę (np. E4 → G4), dla etapu
   odłożonego całą kartę. Wymagania: pola `target` i `gate` w `docs/wymagania.yaml` (pełne
   progi) dla wszystkich `track`.
4. **Sposób pracy:** w `CLAUDE.md` sekcja „Tryb ścieżki pracy” oznaczona jako zakończona;
   obowiązują pełne „Zasady współpracy” (szkic do testu CI, jedna rzecz na PR, triaż
   Graphify i Copilota). `CONTRIBUTING.md`: „Zasady pełne”. Graphify włączony ponownie.
5. **Dokumenty:** `docs/stan-pracy.md` (sekcja „Aktualna ścieżka”), statusy „⏸ odłożone
   (produkt)” w roadmapie zmieniane na ⬜ przy starcie etapu, prompt z sekcji niżej.

## Ścieżka produktu (po przełączeniu): prompt na etap

Wklej poniższy tekst na początku rozmowy, zmieniając numer etapu.

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
**tylko tego projektu**, poza historią git (`.claude/settings.local.json` i
`.claude/hooks/goatcash-guard.py` w katalogu projektu, wykluczone przez `.git/info/exclude`),
są dwie warstwy blokad. Nie działają w żadnym innym projekcie na tym Macu (ustawienia
globalne `~/.claude` są nietknięte). Zmienia je tylko właściciel: katalog `.claude/` jest
objęty regułą `deny` dla narzędzi edycji, a hook odrzuca komendy, które go dotyczą.

1. **Reguły `permissions.deny`** (narzędzia Read, Edit/Write, Grep): `Read` i `Edit` dla
   `//**/.env.local`, `~/.oci/**`, `~/.ssh/**`, `~/.config/sops/age/**`
   (`Read` także `~/Library/Application Support/sops/age/**`); `Edit` dla `/.claude/**`
   (katalog `.claude` projektu); `Bash` dla `gh pr merge *`, `terraform apply *`,
   `terraform destroy *` (i tak samo `tofu`).
2. **Hook `PreToolUse`** `.claude/hooks/goatcash-guard.py`: sprawdza całą treść każdej
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
Hook ma też test 27 przypadków (18 blokowanych, 9 dozwolonych). Tego samego dnia blokady
przeniesiono z `~/.claude` (pierwsza wersja działała globalnie, błąd asystenta) do projektu
i poprawiono fałszywy alarm `2>&1` po `git push`; ponowna próba na żywo (także z worktree
w `.git/claude-wt/`): Read `~/.ssh`, push na `main`, `gh pr merge`, Edit
`.claude/settings.local.json` → odmowa; `git push --dry-run … HEAD:claude/… 2>&1` → dozwolone.

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
zawiera np. `.env.local` (asystent zmienia wtedy plik narzędziem Edit, nie z powłoki).

Mocniejsza warstwa (do decyzji właściciela): sandbox Claude Code (`sandbox.enabled`,
`sandbox.filesystem.denyRead`, `allowUnsandboxedCommands: false`) blokuje odczyt na poziomie
systemu dla komend Bash. Też można go włączyć tylko w ustawieniach tego projektu, ale
domyślnie odcina sieć (lista dozwolonych domen) i wymaga wyjątków dla `gh` i `git push`
przez SSH. Pełna izolacja to osobny użytkownik macOS albo maszyna wirtualna.

## Uwagi z E3 do trybu lokalnego (26.11.2026)

- Hook blokuje każdą komendę Bash, której tekst zawiera frazę o `terraform apply` albo
  `destroy`, także w treści dokumentacji pisanej z powłoki: takie pliki asystent zmienia
  narzędziem Edit/Write.
- Gałąź `claude/…` przed przekazaniem musi stać na **aktualnym** `main`: po scaleniu innego
  PR asystent ją przebazowuje i czeka na nowe CI szkicu; inaczej kontrola
  `git diff --quiet origin/claude/<nazwa> HEAD` u właściciela nie da `IDENTYCZNE`
  (różnica = scalony w międzyczasie PR).
- Terminal właściciela to zsh: komendy z `read -p` i innymi bashizmami asystent opakowuje
  w `bash -c '…'`. Kopiowanie z konsoli do pliku: najpierw uruchomić komendę, która czeka
  (`read`), potem skopiować (wklejenie komendy nadpisuje schowek).
- Minuty GitHub Actions (prywatne repo, macOS ×10, budżet 0 USD = blokada, bez opłat):
  szkice tylko dla gotowych zmian, kilka poprawek w jednym szkicu, gdy dotyczą jednej rzeczy.
- Zmienne Terraform `observability`: mapowanie z nazw w `.env.local`
  (`docs/runbooks/wymiana-serwera.md`, sekcja „Terraform `observability`”).

## Ograniczenia sesji asystenta w chmurze (stan po E2, 23.11.2026)

Dotyczą sesji w chmurze; w trybie lokalnym większość z nich nie występuje. W ścieżce pracy
(od 26.11.2026) sesja w chmurze otwiera **właściwy** PR (nie szkic) i nie przygotowuje łatek;
punkty o szkicach i łatkach niżej dotyczą ścieżki produktu. Gałąź `claude/…` po scaleniu
usuwa właściciel (albo GitHub, gdy w ustawieniach repo jest włączone „Automatically delete
head branches”).

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
