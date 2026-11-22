import { BRAND } from "@/lib/brand";

export default function HomePage() {
  return (
    <main>
      <h1>{BRAND.name}</h1>
      <p>{BRAND.tagline}</p>
      <p>Szkielet aplikacji (etap E1). Funkcje pojawiają się zgodnie z roadmapą.</p>
    </main>
  );
}
