# ADR-0004: Uwierzytelnianie i autoryzacja

- **Status:** proponowana (zatwierdzenie: scalenie PR `docs/E2-adr`)
- **Data:** 2026-11-22
- **Etap:** E2
- **Źródło:** ADR-0001 (Better Auth + JWT przez JWKS), roadmapa E6 (zakres prac 3–4),
  decyzja właściciela z 22.11.2026 o tabelach Better Auth w migracji Alembic

## Kontekst

Konta użytkowników obsługuje Better Auth w `apps/web` (e-mail + hasło, Google OAuth, TOTP,
passkeys), a API w Pythonie musi ufać tożsamości bez współdzielenia sesji ani sekretu. Schemat
bazy ma jedno źródło (Alembic, ADR-0002), ale Better Auth zakłada własny schemat, który może
się zmienić przy aktualizacji biblioteki. Rozjazd ma zostać wykryty automatycznie, zanim
trafi na produkcję.

## Decyzja

1. **Better Auth w `apps/web`** z wbudowanym adapterem Kysely (Postgres), w wersji przypiętej
   dokładnie w `package.json` (bez `^`). Wtyczki: `twoFactor` (TOTP), `passkey`, `jwt`,
   OAuth Google. Sesje w bazie, ciasteczko `HttpOnly`, `Secure`, `SameSite=Lax`.
2. **JWT dla API:** wtyczka `jwt` wydaje token EdDSA (Ed25519), ważny 15 min, z `iss`, `aud`
   (`goatcash-api`), `sub` (UUIDv7 użytkownika) i `role`. FastAPI weryfikuje podpis przez JWKS
   z cache (odświeżanie co 10 min i przy nieznanym `kid`), wymaga `alg = EdDSA` (lista
   dozwolonych, bez `none` i HS*), sprawdza `exp`, `nbf`, `iss`, `aud`.
3. **Autoryzacja w API:** role `user`, `pro_tester`, `admin` z naszej tabeli `roles` (claim
   `role` jest tylko podpowiedzią dla UI; decyzje o uprawnieniach API podejmuje na podstawie
   bazy dla operacji wrażliwych); własność zasobu sprawdza zależność `require_owner` w każdym
   zapytaniu (G6: 0 IDOR).
4. **Tabele Better Auth tworzy migracja Alembic**, nie CLI Better Auth: `user`, `session`,
   `account`, `verification` (roadmapa) oraz tabele wtyczek `two_factor`, `passkey`, `jwks`
   (jawne rozszerzenie, ADR-0002). `better-auth migrate` nie jest uruchamiany w żadnym
   środowisku. Klucze prywatne JWKS w bazie są szyfrowane (opcja wtyczki), a klucz
   szyfrujący jest sekretem aplikacji w SOPS.
5. **Wykrywanie rozjazdu schematu (sprawdzenie `auth-schema-drift` w G2):**
   - CI stawia czysty Postgres w kontenerze i wykonuje `alembic upgrade head`;
   - skrypt w `apps/web` wywołuje `getMigrations(auth.options)` z Better Auth (ta sama
     konfiguracja i ta sama przypięta wersja co aplikacja) na tej bazie;
   - **każdy** niepusty wynik (`toBeCreated`, `toBeAdded`, `toBeAddedIndexes`,
     `unsafeChanges`, `schemaProblems`) kończy sprawdzenie błędem i wypisuje brakujące tabele,
     kolumny i indeksy;
   - kolumny dodane przez nas ponad wymagania Better Auth nie są błędem.
     Skutek: PR Dependabota podbijający Better Auth, który wymaga zmian w schemacie, ma czerwone
     CI, dopóki nie powstanie migracja Alembic dopasowująca schemat. Do zaliczenia G2 to
     sprawdzenie działa w jobie bramki G2; po zaliczeniu wchodzi do `ci-ok` razem z G2.
     Ograniczenie: sprawdzenie widzi tylko to, co Better Auth zgłasza w `getMigrations`; zmianę
     znaczenia istniejącej kolumny wyłapią testy E2E logowania w E6/E12.
6. **Hasła i ochrona kont:** skrót hasła z Better Auth (scrypt), limit prób logowania
   (Valkey, E6), wylogowanie ze wszystkich sesji, 2FA wymagane dla roli `admin`.

## Rozważane alternatywy

| Opcja                                  | Za                         | Przeciw                                                                              |
| -------------------------------------- | -------------------------- | ------------------------------------------------------------------------------------ |
| Tabele tworzy CLI Better Auth          | zawsze zgodne z biblioteką | dwa źródła schematu; zmiany poza przeglądem migracji                                 |
| Adapter Drizzle/Prisma                 | typowany schemat w TS      | `getMigrations` działa tylko z adapterem Kysely, więc brak automatycznego porównania |
| Dostawca (Auth0, Clerk, Supabase Auth) | mniej kodu                 | uzależnienie, koszt po progu, dane użytkowników poza naszą bazą (ADR-0001)           |
| Sesja współdzielona z FastAPI          | bez JWT                    | API zależne od bazy sesji przy każdym zapytaniu; trudniejsza izolacja                |
| Tokeny HS256 ze wspólnym sekretem      | proste                     | sekret w dwóch procesach; każdy z nich może podrobić token                           |

## Konsekwencje

- PR `feat/E2-migracja-0001` tworzy tabele Better Auth; PR z kodem Better Auth (E6) dodaje
  `apps/web/scripts/auth-schema-drift.ts` i cel `make auth-schema-drift`. Do tego czasu
  sprawdzenie `auth-schema-drift` w G2 jest FAIL, więc G2 nie przejdzie bez działającej
  kontroli rozjazdu. Kolejność do ustalenia przy migracji 0001: albo minimalna konfiguracja
  Better Auth już w E2 (tylko do porównania schematu), albo zmiana kryterium G2. Rekomendacja:
  minimalna konfiguracja w E2, bez ekranów logowania.
- Testy w E6: token z innym `aud`, `alg=none`, HS256 podpisany kluczem publicznym, wygasły,
  z nieznanym `kid` → odrzucone.
