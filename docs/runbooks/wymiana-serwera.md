# Runbook: wymiana serwera staging (odtworzenie od zera, F-01)

Kiedy: awaria maszyny A1 lub mikro-VM, uszkodzony system, podejrzenie włamania, test
odtwarzalności G3. Wynik: nowe maszyny i wolumen danych, baza odtworzona z R2, wdrożony
bieżący `main`, w < 30 min bez ręcznych kroków (po jednym „tak”). Źródło: ADR-0007, punkty 1 i 6.

**Zasada Always Free:** w danej chwili tylko jedna A1 2/12. Skrypt najpierw usuwa starą
maszynę, potem tworzy nową; nigdy nie twórz drugiej A1 „obok”.

## Przed startem (raz)

- Klucze chmury w `.env.local` (OCI, Cloudflare, Tailscale: klient OAuth z zakresami
  `auth_keys` i `devices:core`, tag `tag:goatcash-terraform`), `gh` zalogowany, `make tools`.
- Kopie w R2 aktualne: ostatni `restore-test` zielony.
- Środowisko GitHub `staging` bez wymaganego recenzenta (inaczej Ansible i wdrożenie czekają
  na kliknięcie, czyli ręczny krok).

## Kroki

```bash
cd ~/Documents/Millosz/crypto_app
git checkout main && git pull --ff-only
set -a; . ./.env.local; set +a
./scripts/g3_rebuild.sh
```

1. Skrypt pokazuje podsumowanie `terraform plan` (zastąpienie: 2 maszyny, wolumen, załącznik,
   2 klucze Tailscale). Sprawdź, że nic poza tym nie jest usuwane, i wpisz `tak`.
2. Dalej bez udziału: stare węzły Tailscale usunięte, potem Terraform w **trzech fazach**
   (PR #105; Oracle usuwa dyski asynchronicznie, a dysk w stanie TERMINATING nadal zajmuje
   limit 200 GB):
   - **2a:** usunięcie obu maszyn, podłączenia i wolumenu danych; zarezerwowane IP executora
     na ten czas wyjęte ze stanu Terraform (zostaje w OCI, adres się nie zmienia); czekanie,
     aż Oracle usunie wszystkie trzy dyski (wolumen i oba dyski startowe);
   - **2b:** nowe maszyny, wolumen, podłączenie i klucze Tailscale (`-target`, bez IP),
     z kontrolą, że plan usuwa wyłącznie stare klucze Tailscale;
   - **2c:** import zarezerwowanego IP z powrotem do stanu i przepięcie na nowego executora
     (plan: dokładnie 1 zmiana).

   Potem DNS `api.`/`app.` na nowe IP, zmienna `STAGING_PLATFORM_PUBLIC_IP`
   w `staging-readonly`, `ansible-staging.yml`, ponowione wdrożenie HEAD (baza z R2:
   `deploy.sh` czeka na koniec odtwarzania WAL), `/v1/health` z internetu.
3. Ostatnia linia: `== G3 rebuild (local): PASS, <s> s, 0 manual steps ==`. Raport:
   `docs/gates/G3/rebuild-<czas>.log` (dowód G3 `rebuild`: commit w osobnym PR).
4. Po wymianie: `external-scan` i `restore-test` ręcznie (Actions → Run workflow). Nowe
   serwery mają nowe IP: skan z poprzednich adresów nie jest dowodem (rozliczenie E3).

## Zasoby poza Terraform (tworzone ręcznie, odtwarzane ręcznie)

Odtworzenie od zera ich nie dotyka; gdy zginą, odtwarza je właściciel:

| Zasób                                                         | Gdzie jest opisany                                                     |
| ------------------------------------------------------------- | ---------------------------------------------------------------------- |
| bucket stanu `goatcash-tfstate` (wersjonowanie)               | ADR-0007, punkt 2                                                      |
| polityka limitów `goatcash-always-free`, alarm budżetu 1 USD  | ADR-0007, punkty 1 i 6                                                 |
| użytkownik IAM `terraform` i jego klucz API (`~/.oci`)        | roadmapa E0, punkt 3; `rotacja-sekretow.md`                            |
| ACL i `tagOwners` Tailscale                                   | konsola Tailscale; kopia `infra/tailscale/acl.hujson` (ADR-0007 pkt 6) |
| klienty OAuth i OIDC Tailscale                                | `rotacja-sekretow.md`                                                  |
| tokeny Cloudflare, R2, Grafany, Better Stack, bot Telegram    | `rotacja-sekretow.md`                                                  |
| środowiska GitHub `staging` i `staging-readonly`, ich sekrety | ADR-0007, punkt 6                                                      |

## Terraform `observability` (alerty, pulpity, monitory)

Zmienne modułu mają w `.env.local` inne nazwy niż `TF_VAR_…`, a e-maila na alerty tam nie ma
(dane osobowe); komenda `plan` (tylko odczyt) mapuje je i pyta o e-mail w terminalu:

```bash
bash -c 'set -a; . ./.env.local; set +a; read -r -p "E-mail na alerty: " TF_VAR_alert_email; export TF_VAR_alert_email TF_VAR_telegram_bot_token="$TELEGRAM_BOT_TOKEN" TF_VAR_telegram_chat_id="$TELEGRAM_CHAT_ID" TF_VAR_betterstack_api_token="$BETTERSTACK_API_TOKEN"; NS="$(oci os ns get --query data --raw-output)"; terraform -chdir=infra/terraform/observability init -input=false -backend-config="namespace=$NS" >/dev/null && terraform -chdir=infra/terraform/observability plan -input=false -no-color -out=observability.plan'
```

Plik planu zawiera jawne wartości zmiennych (tokeny): `*.plan` jest w `.gitignore`, a po
`terraform apply observability.plan` plik usuwamy (`rm -f infra/terraform/observability/observability.plan`).

## Podejrzenie włamania

Przed wymianą: zrotuj sekrety według `rotacja-sekretow.md` (klucz SSH CI, klucz sondy,
klucz age staging, token R2, hasła baz). Nowy serwer dostaje nowe klucze z nowego
`staging.enc.yaml`. Kopie sprzed incydentu odtwarzaj do czasu sprzed włamania (PITR,
`odtworzenie-z-kopii.md`, część C).

## Gdy coś nie działa

- `terraform apply` odrzuca A1 („Out of host capacity”): region chwilowo bez A1; ponów
  później (nie zmieniaj kształtu bez decyzji kosztowej).
- Węzły nie pojawiają się w Tailscale: konsola szeregowa OCI → `cloud-init status --long`
  i `journalctl -u tailscaled`; klucz jednorazowy wygasa po 1 h (ponów skrypt).
- `ansible-staging.yml` czerwony: popraw rolę, ponów workflow, potem `gh run rerun` wdrożenia.
