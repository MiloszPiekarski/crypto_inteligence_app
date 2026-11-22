import { describe, expect, it } from "vitest";
import { BRAND, pageTitle } from "./brand";

describe("pageTitle", () => {
  it("zwraca samą nazwę marki bez sekcji", () => {
    expect(pageTitle()).toBe("GoatCash");
    expect(pageTitle("   ")).toBe("GoatCash");
  });

  it("łączy sekcję z nazwą marki", () => {
    expect(pageTitle("Rynek")).toBe("Rynek · GoatCash");
  });

  it("używa domeny projektu", () => {
    expect(BRAND.domain).toBe("goatcash.app");
  });
});
