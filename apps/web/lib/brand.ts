/** Podstawowe dane marki używane w nagłówkach i metadanych strony. */
export const BRAND = {
  name: "GoatCash",
  domain: "goatcash.app",
  tagline: "Analiza rynku kryptowalut z przejrzystymi dowodami",
} as const;

/** Tytuł strony w formacie "Sekcja · GoatCash"; pusta sekcja daje samą nazwę marki. */
export function pageTitle(section?: string): string {
  const trimmed = section?.trim();
  return trimmed ? `${trimmed} · ${BRAND.name}` : BRAND.name;
}
