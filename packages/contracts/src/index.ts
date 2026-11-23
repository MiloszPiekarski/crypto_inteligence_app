// Klient API v1 generowany ze specyfikacji OpenAPI (roadmapa E2, „Kontrakty”).
// Typy w `api.ts` powstają poleceniem `pnpm --filter @goatcash/contracts generate`;
// zgodność pliku ze specyfikacją sprawdza `make openapi-lint` (bramka G2).
import createClient from "openapi-fetch";
import type { components, paths } from "./api";

export type { components, paths };
export type Evidence = components["schemas"]["Evidence"];

export function createApiClient(baseUrl: string) {
  return createClient<paths>({ baseUrl });
}
