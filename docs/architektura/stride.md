# Model zagrożeń STRIDE: API, executor, panel administratora

- **Etap:** E2 (roadmapa: „Pozostałe dokumenty etapu”, punkt 3). Data: 2026-11-23.
- **Zakres:** proces `api` (FastAPI, `/v1`) z uwierzytelnianiem Better Auth w `apps/web`,
  executor bota (`services/executor`, osobna VM) i panel administratora (API, E6).
- **Źródła decyzji:** ADR-0002 (role bazy, audyt), ADR-0003 (zdarzenia), ADR-0004 (JWT,
  JWKS, role), ADR-0005 (LLM), ADR-0006 (izolacja executora), Fundamenty sekcja 8.
- **Przegląd:** przy każdej zmianie granic zaufania (nowy proces, nowa integracja) i przed
  bramkami G6, G14b i G15. Stan ✅ tylko z dowodem (test lub raport), ⏳ zaplanowane w etapie.

## Granice zaufania

| Strefa        | Co w niej jest                                                      | Granica                                                               |
| ------------- | ------------------------------------------------------------------- | --------------------------------------------------------------------- |
| Internet      | przeglądarka, boty, atakujący                                       | Cloudflare (TLS, WAF, limity)                                         |
| Frontend      | Next.js + Better Auth (`apps/web`), rola bazy `goatcash_auth`       | sesja w ciasteczku `HttpOnly` → JWT EdDSA 15 min                      |
| Platforma     | `api`, `worker`, `scheduler`, `ingest`, Valkey, rola `goatcash_app` | weryfikacja JWT (JWKS) w `api`; Valkey bez dostępu z internetu        |
| Executor      | `executor` na osobnej mikro-VM, rola `goatcash_executor`, OCI Vault | brak portów przychodzących; tylko Postgres przez Tailscale (ADR-0006) |
| Giełdy        | API giełd użytkowników                                              | klucze bez prawa wypłat, biała lista IP executora                     |
| Administracja | właściciel: SSH przez Tailscale, panel administratora, GitHub       | 2FA, rola `admin` z wymaganym 2FA (ADR-0004)                          |

## Aktywa (co chronimy)

1. Klucze API giełd użytkowników (kradzież = handel na cudzym koncie).
2. Konta i dane osobowe użytkowników (e-mail, kanały powiadomień).
3. Integralność zleceń bota i limitów ryzyka (pieniądze użytkowników).
4. Integralność analiz i Ledgera (wiarygodność produktu i pracy inżynierskiej).
5. Sekrety aplikacji i infrastruktury (SOPS, GitHub Environments).
6. Dostępność usługi.

## API (`api`, Better Auth, JWT)

| STRIDE | Zagrożenie                                                            | Zabezpieczenie                                                                                                                     | Gdzie / kiedy                | Weryfikacja                                                    | Stan                |
| ------ | --------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- | ---------------------------- | -------------------------------------------------------------- | ------------------- |
| S      | Podrobiony token (alg `none`, HS256 z kluczem publicznym, obcy `kid`) | Lista dozwolonych algorytmów (tylko EdDSA), JWKS z cache, sprawdzanie `iss`, `aud`, `exp`, `nbf`                                   | ADR-0004, E6                 | testy tokenów w E6 (ADR-0004, Konsekwencje); F-10              | ⏳                  |
| S      | Przejęcie konta (zgadywanie haseł, wyciek hasła)                      | Limit prób logowania (Valkey), scrypt, TOTP i passkeys, 2FA wymagane dla `admin`                                                   | ADR-0004, E6                 | testy E2E przepływów kont, F-10, F-11                          | ⏳                  |
| T      | Zmiana cudzych danych przez API (IDOR)                                | `require_owner` w każdym zapytaniu, publiczne identyfikatory UUIDv7 zamiast kolejnych liczb                                        | ADR-0002, ADR-0004, E6       | testy IDOR: 0 sukcesów (G6, F-10)                              | ⏳                  |
| T      | Wstrzyknięcie SQL                                                     | Zapytania parametryzowane (SQLAlchemy/psycopg), brak sklejania SQL z danymi wejściowymi; ruff `S608` w CI                          | E1, E6                       | `make lint` w CI; ZAP w G6                                     | ✅ reguła lint w CI |
| R      | Wypieranie się działań (zmiana ustawień, blokada konta)               | `audit_log` tylko do dopisywania, także dla właściciela tabeli                                                                     | ADR-0002, migracja 0001      | `test_audit_log_is_append_only_even_for_owner`                 | ✅                  |
| I      | Wyciek danych osobowych przez API lub logi                            | Modele odpowiedzi z `extra="forbid"` (tylko jawne pola), rola `goatcash_readonly` bez danych osobowych, brak e-maili w zdarzeniach | ADR-0002, ADR-0003, E2       | testy ról w migracji; schemat `alert.triggered` odrzuca e-mail | ✅                  |
| I      | Błędy ujawniające szczegóły implementacji                             | Odpowiedzi błędów RFC 9457 bez śladu stosu                                                                                         | E2 (`goatcash.http_api`), E6 | `test_unimplemented_endpoints_return_problem_501`              | ✅ szkic            |
| D      | Zalanie API zapytaniami                                               | Cloudflare (WAF, limity), limity per użytkownik i IP w Valkey, paginacja z limitem 200                                             | E3, E6                       | k6: 429 po przekroczeniu (F-11), NF-02                         | ⏳                  |
| E      | Zwykły użytkownik wywołuje operacje administratora                    | Role z bazy (nie z claimu JWT) dla operacji wrażliwych                                                                             | ADR-0004, E6                 | testy autoryzacji każdego endpointu (G6)                       | ⏳                  |
| E      | Prompt injection w treściach newsów zmienia działanie systemu         | Treści zewnętrzne tylko jako dane, modele bez narzędzi z efektami ubocznymi, walidacja wyjścia                                     | ADR-0005, E10                | zbiór testów odporności w G10                                  | ⏳                  |

## Executor bota

| STRIDE | Zagrożenie                                                      | Zabezpieczenie                                                                                                                                           | Gdzie / kiedy           | Weryfikacja                                                                            | Stan                             |
| ------ | --------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------- | -------------------------------------------------------------------------------------- | -------------------------------- |
| S      | Podszycie się pod platformę i wstrzyknięcie zlecenia            | Executor nie przyjmuje połączeń; czyta intencje z Postgresa jako `goatcash_executor`; ponowne sprawdzenie ryzyka przed wysłaniem                         | ADR-0006, E14           | testy G14b                                                                             | ⏳                               |
| T      | Zmiana intencji zlecenia po decyzji (np. przez przejęty worker) | Rola `goatcash_app` może tylko dodać intencję, nie zmienić zlecenia; własny silnik ryzyka executora odrzuca intencje poza limitami                       | ADR-0002, ADR-0006      | `test_roles_have_least_privilege` (app nie zmieni `bot.orders`)                        | ✅ uprawnienia, ⏳ silnik ryzyka |
| T      | Klucz z prawem wypłat pozwala wyprowadzić środki                | Odrzucenie przy dodawaniu i ograniczenie CHECK w bazie                                                                                                   | ADR-0006, migracja 0001 | `test_withdraw_permission_key_rejected`                                                | ✅ w bazie                       |
| R      | Brak śladu, kto i dlaczego złożył zlecenie                      | Każde przejście stanu w `bot.bot_events`, `clientOrderId` z identyfikatora intencji                                                                      | ADR-0006, E14           | uzgadnianie z giełdą co 15 s (NF-07)                                                   | ⏳                               |
| I      | Wyciek kluczy giełd (z bazy, logów, pamięci)                    | Szyfrowanie kopertowe (AES-256-GCM, klucz główny w OCI Vault), odszyfrowanie tylko w pamięci executora, filtr logów; app nie czyta kolumn z szyfrogramem | ADR-0006, migracja 0001 | `test_roles_have_least_privilege` (brak odczytu `api_key_enc`, `dek_enc`); F-30 w G14b | ✅ uprawnienia, ⏳ szyfrowanie   |
| D      | Awaria lub zablokowanie executora w trakcie pozycji             | SL/TP po stronie giełdy, kill switch, uzgadnianie stanu, alerty                                                                                          | ADR-0006, E14           | chaos i kill switch ≤ 5 s (G14b, F-29)                                                 | ⏳                               |
| E      | Przejęcie executora przez zależność lub obraz                   | Osobny obraz z minimalnymi zależnościami, zakaz importu modułów platformy (także pośrednio), Trivy w CI, użytkownik bez roota                            | E1, ADR-0006            | import-linter (`executor-indirect` w G1), Trivy w CI                                   | ✅                               |

## Panel administratora

| STRIDE | Zagrożenie                                               | Zabezpieczenie                                                                                   | Gdzie / kiedy           | Weryfikacja                                                           | Stan |
| ------ | -------------------------------------------------------- | ------------------------------------------------------------------------------------------------ | ----------------------- | --------------------------------------------------------------------- | ---- |
| S      | Przejęcie konta administratora                           | 2FA wymagane dla `admin`, krótkie sesje, alert o logowaniu administratora                        | ADR-0004, E6            | test: konto `admin` bez 2FA nie wywoła operacji administracyjnej (G6) | ⏳   |
| T      | Nieuprawniona blokada kont lub zmiana ról                | Operacje tylko przez API z rolą z bazy, każda w `audit_log`                                      | ADR-0002, E6            | testy autoryzacji (G6)                                                | ⏳   |
| R      | Administrator wypiera się użycia globalnego kill switcha | `bot.kill_switches` z `changed_by` i powodem, wpis w `audit_log`                                 | migracja 0001, E14      | test E14                                                              | ⏳   |
| I      | Podgląd danych użytkowników ponad potrzebę               | Panel pokazuje minimum (lista, status), bez kluczy giełd i treści powiadomień                    | E6                      | przegląd w G6                                                         | ⏳   |
| D      | Globalny kill switch użyty przypadkowo                   | Potwierdzenie z podaniem powodu, możliwość cofnięcia, alert do właściciela                       | E14                     | test E14                                                              | ⏳   |
| E      | Eskalacja z panelu do infrastruktury                     | Panel bez dostępu do serwera i sekretów; infrastruktura tylko przez SSH/Tailscale i GitHub z 2FA | E3, Fundamenty sekcja 8 | przegląd w G15 (ASVS)                                                 | ⏳   |

## Ryzyka przyjęte świadomie

- Jeden serwer i jedna osoba obsługi w fazie budowy: awaria serwera = przerwa (NF-03 dopuszcza
  99,5% w becie); łagodzenie: kopie na R2 i odtworzenie < 30 min (F-01, F-02).
- Luka w `gate-guard` (PR może podmienić workflow): naprawa w PR 10a przed zaliczeniem G2
  (`docs/stan-pracy.md`).
