# Mandiriagro & Pakerti Corporate Websites — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create two bilingual (ID/EN) corporate websites — mandiriagro.com (CV Mandiri Agro Cemerlang, onion import distributor) and pakerti.com (CV Tunggal Pratama Pakerti, onion trading company) — as Next.js apps in the kodemeio-react monorepo.

**Architecture:** Clone the `corporate` app pattern (Next.js 16 + next-intl + Tailwind v4 + framer-motion) but simplified: no Sentry, no TanStack Query, no API routes. Each site has 5 pages: Home, About, Products, Services, Contact. Both share identical structure but differ in content, branding, and color scheme.

**Tech Stack:** Next.js 16.2.1, React 19, Tailwind CSS v4, next-intl 4.x, framer-motion, lucide-react

**Repo:** `/home/tgunawan/project/00-new-projects/kodemeio-app/kodemeio-react`

---

## File Structure

### mandiriagro app (`apps/web/mandiriagro/`)

```
apps/web/mandiriagro/
├── package.json
├── next.config.ts
├── tsconfig.json
├── postcss.config.mjs
├── app/
│   ├── layout.tsx                     # Root layout (returns children)
│   ├── globals.css                    # Theme: green/earth tones
│   ├── robots.ts
│   ├── sitemap.ts
│   └── [locale]/
│       ├── layout.tsx                 # Locale layout (providers, header, footer)
│       ├── page.tsx                   # Home page
│       ├── loading.tsx
│       ├── not-found.tsx
│       ├── error.tsx
│       ├── about/page.tsx
│       ├── products/page.tsx
│       ├── services/page.tsx
│       └── contact/page.tsx
├── components/
│   ├── layout/
│   │   ├── header.tsx
│   │   └── footer.tsx
│   ├── providers/
│   │   └── theme-provider.tsx
│   ├── sections/
│   │   ├── hero.tsx
│   │   ├── services-overview.tsx
│   │   ├── products-overview.tsx
│   │   ├── branches.tsx
│   │   ├── values.tsx
│   │   └── contact-cta.tsx
│   └── ui/
│       ├── button.tsx
│       └── card.tsx
├── data/
│   └── company.ts                     # Company info, branches, stats
├── i18n/
│   ├── routing.ts
│   ├── request.ts
│   └── navigation.ts
├── lib/
│   ├── utils.ts
│   └── animations.ts
└── messages/
    ├── en.json
    └── id.json
```

### pakerti app (`apps/web/pakerti/`)

Same structure as mandiriagro, with different:
- `data/company.ts` — Pakerti company info, 1 office (Jakarta)
- `app/globals.css` — amber/warm color scheme
- `messages/en.json` and `messages/id.json` — trading-focused content
- No `components/sections/branches.tsx` (single office shown in footer/contact)

### Docker compose files (`compose/`)

```
compose/
├── docker-compose.mandiriagro.yml
└── docker-compose.pakerti.yml
```

---

## Task 1: Scaffold mandiriagro app skeleton

**Files:**
- Create: `apps/web/mandiriagro/package.json`
- Create: `apps/web/mandiriagro/tsconfig.json`
- Create: `apps/web/mandiriagro/postcss.config.mjs`
- Create: `apps/web/mandiriagro/next.config.ts`
- Create: `apps/web/mandiriagro/app/layout.tsx`
- Create: `apps/web/mandiriagro/app/globals.css`
- Create: `apps/web/mandiriagro/lib/utils.ts`
- Create: `apps/web/mandiriagro/lib/animations.ts`

- [ ] **Step 1: Create package.json**

```json
{
  "name": "@kodemeio/mandiriagro",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "next dev --turbopack --port 4004",
    "build": "next build",
    "start": "next start",
    "lint": "eslint . --max-warnings 0",
    "type-check": "tsc --noEmit"
  },
  "dependencies": {
    "@kodemeio/animations": "workspace:*",
    "@kodemeio/next-ui": "workspace:*",
    "@radix-ui/react-slot": "^1.1.0",
    "class-variance-authority": "^0.7.1",
    "clsx": "^2.1.1",
    "framer-motion": "^12.18.1",
    "lucide-react": "^0.478.0",
    "next": "^16.2.1",
    "next-intl": "^4.8.3",
    "next-themes": "^0.4.6",
    "react": "^19.2.3",
    "react-dom": "^19.2.3",
    "tailwind-merge": "^3.3.0"
  },
  "devDependencies": {
    "@kodemeio/next-eslint-config": "workspace:*",
    "@kodemeio/next-typescript-config": "workspace:*",
    "@tailwindcss/postcss": "^4.1.4",
    "@types/node": "^22.15.0",
    "@types/react": "^19.1.0",
    "@types/react-dom": "^19.1.0",
    "tailwindcss": "^4.1.4",
    "typescript": "^5.9.0"
  }
}
```

- [ ] **Step 2: Create tsconfig.json**

```json
{
  "extends": "@kodemeio/next-typescript-config/nextjs.json",
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./*"]
    }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 3: Create postcss.config.mjs**

```js
/** @type {import('postcss-load-config').Config} */
const config = {
  plugins: {
    "@tailwindcss/postcss": {},
  },
};

export default config;
```

- [ ] **Step 4: Create next.config.ts**

```ts
import createNextIntlPlugin from "next-intl/plugin";
import type { NextConfig } from "next";

const withNextIntl = createNextIntlPlugin("./i18n/request.ts");

const cspDirectives = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-eval' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "font-src 'self' https://fonts.gstatic.com",
  "img-src 'self' data: blob: https:",
  "connect-src 'self'",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "object-src 'none'",
];

const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  transpilePackages: ["@kodemeio/next-ui"],
  images: {
    formats: ["image/avif", "image/webp"],
  },
  experimental: {
    optimizePackageImports: ["lucide-react", "framer-motion"],
  },
  headers: async () => [
    {
      source: "/(.*)",
      headers: [
        { key: "X-Frame-Options", value: "DENY" },
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        { key: "X-DNS-Prefetch-Control", value: "on" },
        {
          key: "Strict-Transport-Security",
          value: "max-age=63072000; includeSubDomains; preload",
        },
        {
          key: "Permissions-Policy",
          value: "camera=(), microphone=(), geolocation=(), interest-cohort=()",
        },
        {
          key: "Content-Security-Policy",
          value: cspDirectives.join("; "),
        },
      ],
    },
  ],
};

export default withNextIntl(nextConfig);
```

- [ ] **Step 5: Create app/layout.tsx**

```tsx
import type { ReactNode } from "react";

export default function RootLayout({ children }: { children: ReactNode }) {
  return children;
}
```

- [ ] **Step 6: Create app/globals.css — green/earth theme for agri-business**

```css
@import "tailwindcss";

@custom-variant dark (&:is(.dark *));

/* ========================================
   MANDIRI AGRO CEMERLANG - Earth Green
   Professional agri-business design
   ======================================== */

@theme inline {
  --radius-sm: calc(var(--radius) - 4px);
  --radius-md: calc(var(--radius) - 2px);
  --radius-lg: var(--radius);
  --radius-xl: calc(var(--radius) + 4px);
  --radius-2xl: calc(var(--radius) + 8px);

  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --color-card: var(--card);
  --color-card-foreground: var(--card-foreground);
  --color-popover: var(--popover);
  --color-popover-foreground: var(--popover-foreground);
  --color-primary: var(--primary);
  --color-primary-foreground: var(--primary-foreground);
  --color-secondary: var(--secondary);
  --color-secondary-foreground: var(--secondary-foreground);
  --color-muted: var(--muted);
  --color-muted-foreground: var(--muted-foreground);
  --color-accent: var(--accent);
  --color-accent-foreground: var(--accent-foreground);
  --color-destructive: var(--destructive);
  --color-border: var(--border);
  --color-input: var(--input);
  --color-ring: var(--ring);

  --color-brand: var(--brand);
  --color-brand-foreground: var(--brand-foreground);

  --font-sans: "Inter Variable", "Inter", ui-sans-serif, system-ui, sans-serif;
  --font-mono: ui-monospace, monospace;
}

:root {
  --radius: 0.625rem;

  --background: oklch(0.985 0.005 145);
  --foreground: oklch(0.145 0.03 145);

  --card: oklch(0.995 0.003 145);
  --card-foreground: oklch(0.145 0.03 145);

  --popover: oklch(0.995 0.003 145);
  --popover-foreground: oklch(0.145 0.03 145);

  --primary: oklch(0.205 0.03 145);
  --primary-foreground: oklch(0.985 0.005 145);

  --secondary: oklch(0.945 0.015 145);
  --secondary-foreground: oklch(0.205 0.03 145);

  --muted: oklch(0.955 0.012 145);
  --muted-foreground: oklch(0.45 0.03 145);

  --accent: oklch(0.945 0.015 145);
  --accent-foreground: oklch(0.205 0.03 145);

  --brand: oklch(0.50 0.16 145);
  --brand-foreground: oklch(0.98 0.005 145);

  --destructive: oklch(0.577 0.245 27.325);

  --border: oklch(0.9 0.012 145);
  --input: oklch(0.9 0.012 145);
  --ring: oklch(0.50 0.16 145);
}

.dark {
  --background: oklch(0.115 0.02 145);
  --foreground: oklch(0.945 0.01 145);

  --card: oklch(0.145 0.025 145);
  --card-foreground: oklch(0.945 0.01 145);

  --popover: oklch(0.145 0.025 145);
  --popover-foreground: oklch(0.945 0.01 145);

  --primary: oklch(0.945 0.01 145);
  --primary-foreground: oklch(0.115 0.02 145);

  --secondary: oklch(0.185 0.025 145);
  --secondary-foreground: oklch(0.945 0.01 145);

  --muted: oklch(0.185 0.025 145);
  --muted-foreground: oklch(0.6 0.02 145);

  --accent: oklch(0.185 0.025 145);
  --accent-foreground: oklch(0.945 0.01 145);

  --brand: oklch(0.60 0.14 145);
  --brand-foreground: oklch(0.115 0.02 145);

  --border: oklch(0.22 0.025 145);
  --input: oklch(0.22 0.025 145);
  --ring: oklch(0.60 0.14 145);
}

@layer base {
  * {
    @apply border-border outline-ring/50;
  }

  html {
    scroll-behavior: smooth;
  }

  body {
    @apply bg-background text-foreground antialiased;
    font-feature-settings: "rlig" 1, "calt" 1;
  }

  ::selection {
    @apply bg-brand/20 text-foreground;
  }
}

@layer components {
  .glass {
    @apply bg-background/80 backdrop-blur-xl border border-border/50;
  }

  .dark .glass {
    @apply bg-background/60 border-border/30;
  }
}

@layer utilities {
  @media (prefers-reduced-motion: reduce) {
    *,
    ::before,
    ::after {
      animation-duration: 0.01ms !important;
      animation-iteration-count: 1 !important;
      transition-duration: 0.01ms !important;
    }
  }
}
```

- [ ] **Step 7: Create lib/utils.ts and lib/animations.ts**

`lib/utils.ts`:
```ts
import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
```

`lib/animations.ts`:
```ts
export {
  fadeIn,
  fadeInUp,
  fadeInDown,
  fadeInLeft,
  fadeInRight,
  staggerContainer,
  scaleIn,
  heroTitle,
  heroSubtitle,
} from "@kodemeio/animations";
```

- [ ] **Step 8: Commit**

```bash
git add apps/web/mandiriagro/
git commit -m "feat(mandiriagro): scaffold Next.js app skeleton"
```

---

## Task 2: Add i18n and translation files for mandiriagro

**Files:**
- Create: `apps/web/mandiriagro/i18n/routing.ts`
- Create: `apps/web/mandiriagro/i18n/request.ts`
- Create: `apps/web/mandiriagro/i18n/navigation.ts`
- Create: `apps/web/mandiriagro/messages/en.json`
- Create: `apps/web/mandiriagro/messages/id.json`

- [ ] **Step 1: Create i18n/routing.ts**

```ts
import { defineRouting } from "next-intl/routing";

export const routing = defineRouting({
  locales: ["en", "id"],
  defaultLocale: "en",
  localePrefix: "as-needed",
});
```

- [ ] **Step 2: Create i18n/request.ts**

```ts
import { getRequestConfig } from "next-intl/server";
import { routing } from "./routing";

export default getRequestConfig(async ({ requestLocale }) => {
  let locale = await requestLocale;

  if (!locale || !routing.locales.includes(locale as "en" | "id")) {
    locale = routing.defaultLocale;
  }

  return {
    locale,
    messages: (await import(`../messages/${locale}.json`)).default,
  };
});
```

- [ ] **Step 3: Create i18n/navigation.ts**

```ts
import { createNavigation } from "next-intl/navigation";
import { routing } from "./routing";

export const { Link, redirect, usePathname, useRouter, getPathname } =
  createNavigation(routing);
```

- [ ] **Step 4: Create messages/en.json**

```json
{
  "common": {
    "toggleTheme": "Toggle theme",
    "getInTouch": "Get in Touch",
    "openMenu": "Open menu",
    "closeMenu": "Close menu",
    "learnMore": "Learn More",
    "viewAll": "View All"
  },
  "nav": {
    "home": "Home",
    "about": "About",
    "products": "Products",
    "services": "Services",
    "contact": "Contact"
  },
  "hero": {
    "badge": "Trusted Imported Onion Distributor",
    "title": "Indonesia's Reliable <highlight>Onion Distribution</highlight> Network",
    "description": "CV Mandiri Agro Cemerlang distributes premium imported onions across Indonesia through 7 strategically located branches — ensuring fresh supply from farm to market.",
    "cta": "Contact Us",
    "ctaSecondary": "Our Products"
  },
  "services": {
    "title": "Our Services",
    "subtitle": "End-to-end onion distribution — from port to your warehouse",
    "coldStorage": {
      "title": "Cold Storage",
      "description": "Temperature-controlled warehousing (0-4°C) across all 7 branches, ensuring optimal freshness and extended shelf life for imported onions."
    },
    "grading": {
      "title": "Sorting & Grading",
      "description": "Professional sortasi by size (S/M/L/XL) and quality grade (A/B/C), meeting the exact specifications of modern retail and food processors."
    },
    "distribution": {
      "title": "Nationwide Distribution",
      "description": "Refrigerated logistics fleet covering Java, Sumatra, and Sulawesi — reliable delivery from our branches to wholesale markets, retailers, and food processors."
    },
    "supplyGuarantee": {
      "title": "Supply Guarantee",
      "description": "Contracted supply commitments backed by multi-origin sourcing from India, China, and Egypt. Consistent stock even during peak demand seasons."
    }
  },
  "products": {
    "title": "Our Products",
    "subtitle": "Premium imported onions for every market segment",
    "bombay": {
      "title": "Bawang Bombay",
      "subtitle": "Yellow/Brown Onions",
      "description": "Large round onions imported from India, China, and Egypt. Used widely in food processing, HoReCa, and modern retail. Available in 10-25kg mesh bags.",
      "origins": "India, China, Egypt, Netherlands"
    },
    "putih": {
      "title": "Bawang Putih",
      "subtitle": "Garlic",
      "description": "Premium garlic sourced primarily from China and India. Essential ingredient in Indonesian cuisine, supplied in bulk for wholesalers and food manufacturers.",
      "origins": "China, India, Vietnam"
    },
    "merah": {
      "title": "Bawang Merah",
      "subtitle": "Imported Shallots",
      "description": "Seasonal imported shallots to supplement domestic supply during off-season. Sourced from India, Thailand, and Vietnam.",
      "origins": "India, Thailand, Vietnam"
    }
  },
  "branches": {
    "title": "Our Branches",
    "subtitle": "7 strategically located distribution centers across Indonesia",
    "jakarta": { "name": "Jakarta", "description": "Head office & main distribution hub — Tanjung Priok port access" },
    "bandung": { "name": "Bandung", "description": "West Java distribution center — serving Bandung Raya & Priangan" },
    "solo": { "name": "Solo", "description": "Central Java hub — covering Solo, Semarang & surrounding regions" },
    "surabaya": { "name": "Surabaya", "description": "East Java distribution center — Tanjung Perak port access" },
    "medan1": { "name": "Medan 1", "description": "North Sumatra main branch — Belawan port access" },
    "medan2": { "name": "Medan 2", "description": "North Sumatra secondary branch — extended coverage" },
    "makassar": { "name": "Makassar", "description": "Eastern Indonesia hub — serving Sulawesi & eastern regions" }
  },
  "about": {
    "title": "About Us",
    "subtitle": "CV Mandiri Agro Cemerlang",
    "description": "We are a leading imported onion distributor in Indonesia, connecting global suppliers with local markets through our nationwide network of cold storage facilities and distribution centers.",
    "mission": {
      "title": "Our Mission",
      "description": "To provide a reliable, nationwide supply chain for premium imported onions — ensuring freshness, competitive pricing, and consistent availability for wholesalers, retailers, and food processors across Indonesia."
    },
    "vision": {
      "title": "Our Vision",
      "description": "To become Indonesia's most trusted onion distribution network, setting the standard for quality, reliability, and supply chain efficiency in the agricultural commodities sector."
    }
  },
  "values": {
    "title": "Our Values",
    "freshness": {
      "title": "Freshness Guaranteed",
      "description": "Cold chain integrity from port to delivery. Every branch maintains temperature-controlled storage to preserve quality."
    },
    "reliability": {
      "title": "Supply Reliability",
      "description": "Multi-origin sourcing strategy ensures consistent stock. We deliver on time, every time — even during Ramadan peak demand."
    },
    "reach": {
      "title": "Nationwide Reach",
      "description": "7 branches across Indonesia's major economic corridors. From Medan to Makassar, we're where our customers need us."
    },
    "partnership": {
      "title": "Long-term Partnership",
      "description": "We build lasting relationships with suppliers and customers alike, based on trust, transparency, and mutual growth."
    }
  },
  "contact": {
    "title": "Contact Us",
    "subtitle": "Get in touch for pricing, supply inquiries, or partnership opportunities",
    "email": "Email",
    "phone": "Phone",
    "address": "Head Office",
    "form": {
      "name": "Full Name",
      "company": "Company Name",
      "email": "Email Address",
      "phone": "Phone Number",
      "message": "Message",
      "submit": "Send Message",
      "success": "Thank you! We'll get back to you shortly.",
      "namePlaceholder": "Your name",
      "companyPlaceholder": "Your company",
      "emailPlaceholder": "your@email.com",
      "phonePlaceholder": "+62...",
      "messagePlaceholder": "Tell us about your requirements..."
    }
  },
  "cta": {
    "title": "Ready to Secure Your Onion Supply?",
    "description": "Contact us for competitive pricing, reliable delivery, and consistent quality across Indonesia.",
    "button": "Get a Quote"
  },
  "footer": {
    "services": "Services",
    "company": "Company",
    "legal": "Legal",
    "privacyPolicy": "Privacy Policy",
    "termsOfService": "Terms of Service",
    "allRightsReserved": "All rights reserved."
  },
  "notFound": {
    "title": "Page Not Found",
    "description": "The page you're looking for doesn't exist.",
    "backHome": "Back to Home"
  },
  "error": {
    "title": "Something went wrong",
    "description": "An unexpected error occurred.",
    "retry": "Try Again"
  }
}
```

- [ ] **Step 5: Create messages/id.json**

```json
{
  "common": {
    "toggleTheme": "Ganti tema",
    "getInTouch": "Hubungi Kami",
    "openMenu": "Buka menu",
    "closeMenu": "Tutup menu",
    "learnMore": "Selengkapnya",
    "viewAll": "Lihat Semua"
  },
  "nav": {
    "home": "Beranda",
    "about": "Tentang",
    "products": "Produk",
    "services": "Layanan",
    "contact": "Kontak"
  },
  "hero": {
    "badge": "Distributor Bawang Impor Terpercaya",
    "title": "Jaringan <highlight>Distribusi Bawang</highlight> Terpercaya di Indonesia",
    "description": "CV Mandiri Agro Cemerlang mendistribusikan bawang impor berkualitas ke seluruh Indonesia melalui 7 cabang strategis — memastikan pasokan segar dari pelabuhan ke pasar.",
    "cta": "Hubungi Kami",
    "ctaSecondary": "Produk Kami"
  },
  "services": {
    "title": "Layanan Kami",
    "subtitle": "Distribusi bawang menyeluruh — dari pelabuhan ke gudang Anda",
    "coldStorage": {
      "title": "Gudang Pendingin",
      "description": "Penyimpanan bersuhu terkontrol (0-4°C) di seluruh 7 cabang, menjamin kesegaran optimal dan umur simpan lebih lama untuk bawang impor."
    },
    "grading": {
      "title": "Sortasi & Grading",
      "description": "Sortasi profesional berdasarkan ukuran (S/M/L/XL) dan kualitas (Grade A/B/C), memenuhi spesifikasi ritel modern dan industri pengolahan makanan."
    },
    "distribution": {
      "title": "Distribusi Nasional",
      "description": "Armada logistik berpendingin melayani Jawa, Sumatera, dan Sulawesi — pengiriman handal dari cabang kami ke pasar induk, pengecer, dan pabrik pengolahan."
    },
    "supplyGuarantee": {
      "title": "Jaminan Pasokan",
      "description": "Komitmen pasokan terkontrak didukung sumber multi-negara dari India, China, dan Mesir. Stok konsisten bahkan saat musim permintaan puncak."
    }
  },
  "products": {
    "title": "Produk Kami",
    "subtitle": "Bawang impor premium untuk setiap segmen pasar",
    "bombay": {
      "title": "Bawang Bombay",
      "subtitle": "Bawang Kuning/Coklat",
      "description": "Bawang bulat besar diimpor dari India, China, dan Mesir. Banyak digunakan dalam industri pengolahan makanan, HoReCa, dan ritel modern. Tersedia dalam karung jaring 10-25kg.",
      "origins": "India, China, Mesir, Belanda"
    },
    "putih": {
      "title": "Bawang Putih",
      "subtitle": "Garlic",
      "description": "Bawang putih premium bersumber utama dari China dan India. Bahan esensial masakan Indonesia, dipasok dalam jumlah besar untuk grosir dan produsen makanan.",
      "origins": "China, India, Vietnam"
    },
    "merah": {
      "title": "Bawang Merah",
      "subtitle": "Bawang Merah Impor",
      "description": "Bawang merah impor musiman untuk melengkapi pasokan domestik saat musim paceklik. Bersumber dari India, Thailand, dan Vietnam.",
      "origins": "India, Thailand, Vietnam"
    }
  },
  "branches": {
    "title": "Cabang Kami",
    "subtitle": "7 pusat distribusi strategis di seluruh Indonesia",
    "jakarta": { "name": "Jakarta", "description": "Kantor pusat & hub distribusi utama — akses Pelabuhan Tanjung Priok" },
    "bandung": { "name": "Bandung", "description": "Pusat distribusi Jawa Barat — melayani Bandung Raya & Priangan" },
    "solo": { "name": "Solo", "description": "Hub Jawa Tengah — melayani Solo, Semarang & sekitarnya" },
    "surabaya": { "name": "Surabaya", "description": "Pusat distribusi Jawa Timur — akses Pelabuhan Tanjung Perak" },
    "medan1": { "name": "Medan 1", "description": "Cabang utama Sumatera Utara — akses Pelabuhan Belawan" },
    "medan2": { "name": "Medan 2", "description": "Cabang kedua Sumatera Utara — jangkauan diperluas" },
    "makassar": { "name": "Makassar", "description": "Hub Indonesia Timur — melayani Sulawesi & wilayah timur" }
  },
  "about": {
    "title": "Tentang Kami",
    "subtitle": "CV Mandiri Agro Cemerlang",
    "description": "Kami adalah distributor bawang impor terkemuka di Indonesia, menghubungkan pemasok global dengan pasar lokal melalui jaringan gudang pendingin dan pusat distribusi nasional.",
    "mission": {
      "title": "Misi Kami",
      "description": "Menyediakan rantai pasok bawang impor premium yang handal dan berskala nasional — menjamin kesegaran, harga kompetitif, dan ketersediaan konsisten bagi pedagang besar, pengecer, dan industri pengolahan makanan di seluruh Indonesia."
    },
    "vision": {
      "title": "Visi Kami",
      "description": "Menjadi jaringan distribusi bawang paling terpercaya di Indonesia, menetapkan standar kualitas, kehandalan, dan efisiensi rantai pasok di sektor komoditas pertanian."
    }
  },
  "values": {
    "title": "Nilai Kami",
    "freshness": {
      "title": "Jaminan Kesegaran",
      "description": "Integritas rantai dingin dari pelabuhan hingga pengiriman. Setiap cabang memiliki penyimpanan bersuhu terkontrol untuk menjaga kualitas."
    },
    "reliability": {
      "title": "Kehandalan Pasokan",
      "description": "Strategi sumber multi-negara memastikan stok konsisten. Kami mengirim tepat waktu, setiap saat — bahkan saat puncak permintaan Ramadan."
    },
    "reach": {
      "title": "Jangkauan Nasional",
      "description": "7 cabang di koridor ekonomi utama Indonesia. Dari Medan hingga Makassar, kami hadir di mana pelanggan membutuhkan."
    },
    "partnership": {
      "title": "Kemitraan Jangka Panjang",
      "description": "Kami membangun hubungan berkelanjutan dengan pemasok dan pelanggan, berdasarkan kepercayaan, transparansi, dan pertumbuhan bersama."
    }
  },
  "contact": {
    "title": "Hubungi Kami",
    "subtitle": "Hubungi kami untuk penawaran harga, pertanyaan pasokan, atau peluang kerjasama",
    "email": "Email",
    "phone": "Telepon",
    "address": "Kantor Pusat",
    "form": {
      "name": "Nama Lengkap",
      "company": "Nama Perusahaan",
      "email": "Alamat Email",
      "phone": "Nomor Telepon",
      "message": "Pesan",
      "submit": "Kirim Pesan",
      "success": "Terima kasih! Kami akan segera menghubungi Anda.",
      "namePlaceholder": "Nama Anda",
      "companyPlaceholder": "Perusahaan Anda",
      "emailPlaceholder": "email@anda.com",
      "phonePlaceholder": "+62...",
      "messagePlaceholder": "Ceritakan kebutuhan Anda..."
    }
  },
  "cta": {
    "title": "Siap Mengamankan Pasokan Bawang Anda?",
    "description": "Hubungi kami untuk harga kompetitif, pengiriman handal, dan kualitas konsisten di seluruh Indonesia.",
    "button": "Minta Penawaran"
  },
  "footer": {
    "services": "Layanan",
    "company": "Perusahaan",
    "legal": "Legal",
    "privacyPolicy": "Kebijakan Privasi",
    "termsOfService": "Syarat & Ketentuan",
    "allRightsReserved": "Hak cipta dilindungi."
  },
  "notFound": {
    "title": "Halaman Tidak Ditemukan",
    "description": "Halaman yang Anda cari tidak tersedia.",
    "backHome": "Kembali ke Beranda"
  },
  "error": {
    "title": "Terjadi Kesalahan",
    "description": "Terjadi kesalahan yang tidak terduga.",
    "retry": "Coba Lagi"
  }
}
```

- [ ] **Step 6: Commit**

```bash
git add apps/web/mandiriagro/i18n/ apps/web/mandiriagro/messages/
git commit -m "feat(mandiriagro): add i18n routing and bilingual translations"
```

---

## Task 3: Add company data and UI components for mandiriagro

**Files:**
- Create: `apps/web/mandiriagro/data/company.ts`
- Create: `apps/web/mandiriagro/components/ui/button.tsx`
- Create: `apps/web/mandiriagro/components/ui/card.tsx`
- Create: `apps/web/mandiriagro/components/providers/theme-provider.tsx`

- [ ] **Step 1: Create data/company.ts**

```ts
export interface Branch {
  id: string;
  city: string;
  description: string;
  isHQ: boolean;
}

export interface Product {
  id: string;
  icon: string;
}

export interface Stat {
  label: string;
  value: string;
  suffix?: string;
}

export const companyInfo = {
  name: "Mandiri Agro Cemerlang",
  legalName: "CV Mandiri Agro Cemerlang",
  tagline: "Distributor Bawang Impor Terpercaya",
  description:
    "Leading imported onion distributor in Indonesia with 7 branches across the archipelago. Cold storage, grading, and nationwide logistics.",
  email: "info@mandiriagro.com",
  phone: "+62 21 1234 5678",
  location: "Jakarta, Indonesia",
  website: "https://mandiriagro.com",
} as const;

export const stats: Stat[] = [
  { label: "Branches", value: "7" },
  { label: "Tons/Year", value: "50K", suffix: "+" },
  { label: "Supply Origins", value: "5", suffix: "+" },
  { label: "Years Operating", value: "10", suffix: "+" },
];

export const branches: Branch[] = [
  { id: "jakarta", city: "Jakarta", description: "Head office & main distribution hub", isHQ: true },
  { id: "bandung", city: "Bandung", description: "West Java distribution center", isHQ: false },
  { id: "solo", city: "Solo", description: "Central Java hub", isHQ: false },
  { id: "surabaya", city: "Surabaya", description: "East Java distribution center", isHQ: false },
  { id: "medan1", city: "Medan 1", description: "North Sumatra main branch", isHQ: false },
  { id: "medan2", city: "Medan 2", description: "North Sumatra secondary branch", isHQ: false },
  { id: "makassar", city: "Makassar", description: "Eastern Indonesia hub", isHQ: false },
];

export const values = [
  { title: "Freshness Guaranteed", icon: "thermometer-snowflake" },
  { title: "Supply Reliability", icon: "truck" },
  { title: "Nationwide Reach", icon: "map-pin" },
  { title: "Long-term Partnership", icon: "handshake" },
];
```

- [ ] **Step 2: Copy UI components from corporate (button.tsx, card.tsx, theme-provider.tsx)**

These are identical to the corporate app's versions — standard shadcn components.

`components/ui/button.tsx` — copy from `apps/web/corporate/components/ui/button.tsx` verbatim.

`components/ui/card.tsx` — copy from `apps/web/corporate/components/ui/card.tsx` verbatim.

`components/providers/theme-provider.tsx` — copy from `apps/web/corporate/components/providers/theme-provider.tsx` verbatim.

- [ ] **Step 3: Commit**

```bash
git add apps/web/mandiriagro/data/ apps/web/mandiriagro/components/
git commit -m "feat(mandiriagro): add company data and UI components"
```

---

## Task 4: Build locale layout, pages, header, and footer for mandiriagro

**Files:**
- Create: `apps/web/mandiriagro/app/[locale]/layout.tsx`
- Create: `apps/web/mandiriagro/app/[locale]/page.tsx`
- Create: `apps/web/mandiriagro/app/[locale]/loading.tsx`
- Create: `apps/web/mandiriagro/app/[locale]/not-found.tsx`
- Create: `apps/web/mandiriagro/app/[locale]/error.tsx`
- Create: `apps/web/mandiriagro/app/[locale]/about/page.tsx`
- Create: `apps/web/mandiriagro/app/[locale]/products/page.tsx`
- Create: `apps/web/mandiriagro/app/[locale]/services/page.tsx`
- Create: `apps/web/mandiriagro/app/[locale]/contact/page.tsx`
- Create: `apps/web/mandiriagro/app/robots.ts`
- Create: `apps/web/mandiriagro/app/sitemap.ts`
- Create: `apps/web/mandiriagro/components/layout/header.tsx`
- Create: `apps/web/mandiriagro/components/layout/footer.tsx`
- Create: `apps/web/mandiriagro/components/sections/hero.tsx`
- Create: `apps/web/mandiriagro/components/sections/services-overview.tsx`
- Create: `apps/web/mandiriagro/components/sections/products-overview.tsx`
- Create: `apps/web/mandiriagro/components/sections/branches.tsx`
- Create: `apps/web/mandiriagro/components/sections/values.tsx`
- Create: `apps/web/mandiriagro/components/sections/contact-cta.tsx`

This is the largest task. The locale layout follows the corporate pattern but simplified (no Sentry, no QueryProvider). Header has 5 nav items (Home, About, Products, Services, Contact). Footer shows company info with branch count.

All section components follow the corporate pattern: `"use client"`, framer-motion animations, useTranslations hook, lucide-react icons.

The home page composition:
```tsx
<Hero />
<ServicesOverview />
<ProductsOverview />
<Branches />
<Values />
<ContactCTA />
```

The About page shows mission, vision, and values.
The Products page shows the 3 product cards (Bombay, Putih, Merah) with origins.
The Services page shows the 4 service cards (Cold Storage, Grading, Distribution, Supply Guarantee).
The Contact page shows a contact form + branch locations.

- [ ] **Step 1: Create locale layout, loading, not-found, error pages**
- [ ] **Step 2: Create header component** (adapted from corporate — 5 nav items, company name "Mandiri Agro")
- [ ] **Step 3: Create footer component** (adapted — show branch count, onion-specific links)
- [ ] **Step 4: Create hero section** (adapted — onion distribution messaging, green brand)
- [ ] **Step 5: Create services-overview section** (4 cards: cold storage, grading, distribution, supply)
- [ ] **Step 6: Create products-overview section** (3 cards: bombay, putih, merah with origin countries)
- [ ] **Step 7: Create branches section** (7-item grid with MapPin icons)
- [ ] **Step 8: Create values and contact-cta sections**
- [ ] **Step 9: Create home page composing all sections**
- [ ] **Step 10: Create about, products, services, contact pages**
- [ ] **Step 11: Create robots.ts and sitemap.ts**
- [ ] **Step 12: Verify dev server starts**

Run: `cd apps/web/mandiriagro && pnpm install && pnpm dev`
Expected: Dev server on http://localhost:4004 with bilingual corporate site

- [ ] **Step 13: Commit**

```bash
git add apps/web/mandiriagro/
git commit -m "feat(mandiriagro): complete corporate website with all pages and sections"
```

---

## Task 5: Create pakerti app by cloning mandiriagro

**Files:**
- Create: `apps/web/pakerti/` (full directory — clone from mandiriagro)

- [ ] **Step 1: Copy mandiriagro to pakerti**

```bash
cp -r apps/web/mandiriagro apps/web/pakerti
```

- [ ] **Step 2: Update package.json**

Change name to `@kodemeio/pakerti`, dev port to `4005`.

- [ ] **Step 3: Update globals.css — amber/warm color scheme**

Replace oklch hue from `145` (green) to `65` (amber/warm gold) throughout the file. Comment to "TUNGGAL PRATAMA PAKERTI - Warm Amber".

- [ ] **Step 4: Update data/company.ts**

```ts
export const companyInfo = {
  name: "Tunggal Pratama Pakerti",
  legalName: "CV Tunggal Pratama Pakerti",
  tagline: "Trading Bawang Berkualitas Global",
  description:
    "International onion trading company specializing in global sourcing, import documentation, and quality control at origin.",
  email: "info@pakerti.com",
  phone: "+62 21 9876 5432",
  location: "Jakarta, Indonesia",
  website: "https://pakerti.com",
} as const;

export const stats: Stat[] = [
  { label: "Source Countries", value: "8", suffix: "+" },
  { label: "Tons Traded/Year", value: "30K", suffix: "+" },
  { label: "Import Permits", value: "100", suffix: "+" },
  { label: "Years Experience", value: "8", suffix: "+" },
];

// No branches array — single office
```

- [ ] **Step 5: Update messages/en.json and messages/id.json**

Replace all content with trading-focused copy:
- Hero: "Global Onion Sourcing & Trading" / "Perdagangan Bawang Global"
- Services: Sourcing & Procurement, Import Documentation (RIPH/SPI), Quality Control at Origin, Price & Risk Management
- Products: Same 3 products but emphasis on bulk import volumes and FOB/CIF pricing
- Remove branches section (single office — show in contact/footer)
- About: Trading company mission/vision
- Contact: Single Jakarta office

- [ ] **Step 6: Update next.config.ts site URL reference**

Change any `mandiriagro.com` references to `pakerti.com`.

- [ ] **Step 7: Remove branches section component and update home page**

Delete `components/sections/branches.tsx`. Update home page to:
```tsx
<Hero />
<ServicesOverview />
<ProductsOverview />
<Values />
<ContactCTA />
```

- [ ] **Step 8: Verify dev server starts**

Run: `cd apps/web/pakerti && pnpm install && pnpm dev`
Expected: Dev server on http://localhost:4005 with amber-themed trading site

- [ ] **Step 9: Commit**

```bash
git add apps/web/pakerti/
git commit -m "feat(pakerti): create corporate website for onion trading company"
```

---

## Task 6: Create docker-compose files and update deploy manifests

**Files:**
- Create: `compose/docker-compose.mandiriagro.yml` (in kodemeio-react repo)
- Create: `compose/docker-compose.pakerti.yml` (in kodemeio-react repo)
- Modify: `deploys/instances/mandiriagro.com-nextjs-web.yaml` (in kodemeio-platform repo)
- Modify: `deploys/instances/pakerti.com-nextjs-web.yaml` (in kodemeio-platform repo)

- [ ] **Step 1: Create compose/docker-compose.mandiriagro.yml**

```yaml
# =============================================================================
# Mandiri Agro — Corporate Website (Dokploy)
# =============================================================================

networks:
  dokploy-network:
    external: true

services:
  mandiriagro-web:
    build:
      context: ..
      dockerfile: Dockerfile.next
      args:
        APP_NAME: mandiriagro
        APP_PORT: "3000"
        NEXT_PUBLIC_SITE_URL: "${NEXT_PUBLIC_SITE_URL:-https://mandiriagro.com}"
    restart: unless-stopped
    networks:
      - dokploy-network
    environment:
      NODE_ENV: production
      TZ: "${TZ:-Asia/Jakarta}"
      NEXT_PUBLIC_SITE_URL: "${NEXT_PUBLIC_SITE_URL:-https://mandiriagro.com}"
    deploy:
      resources:
        limits:
          cpus: "${WEB_CPU_LIMIT:-0.5}"
          memory: "${WEB_MEMORY_LIMIT:-512M}"
        reservations:
          memory: 128M
    labels:
      - "logging=promtail"
      - "app=mandiriagro-web"
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://127.0.0.1:3000/"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 15s
```

- [ ] **Step 2: Create compose/docker-compose.pakerti.yml**

Same structure, replace `mandiriagro` with `pakerti` and site URL with `pakerti.com`.

- [ ] **Step 3: Update kodemeio-platform deploy manifests**

Update `deploys/instances/mandiriagro.com-nextjs-web.yaml`:
- Ensure `source_overrides.compose_path` = `compose/docker-compose.mandiriagro.yml`
- Ensure `domain.service` = `mandiriagro-web` (must match docker-compose service name)

Update `deploys/instances/pakerti.com-nextjs-web.yaml`:
- Ensure `source_overrides.compose_path` = `compose/docker-compose.pakerti.yml`
- Ensure `domain.service` = `pakerti-web` (must match docker-compose service name)

- [ ] **Step 4: Commit both repos**

```bash
# In kodemeio-react
git add compose/docker-compose.mandiriagro.yml compose/docker-compose.pakerti.yml
git commit -m "feat: add docker-compose for mandiriagro and pakerti websites"

# In kodemeio-platform
git add deploys/instances/mandiriagro.com-nextjs-web.yaml deploys/instances/pakerti.com-nextjs-web.yaml
git commit -m "fix(deploy): update mandiriagro and pakerti manifests with correct compose paths"
```

---

## Task 7: Add public assets (favicon, OG image placeholders)

**Files:**
- Create: `apps/web/mandiriagro/public/favicon.ico` (placeholder)
- Create: `apps/web/mandiriagro/public/og-image.png` (placeholder)
- Create: `apps/web/pakerti/public/favicon.ico` (placeholder)
- Create: `apps/web/pakerti/public/og-image.png` (placeholder)

- [ ] **Step 1: Create placeholder public directories with minimal favicon**

Use a simple SVG favicon for now. Both can be replaced later with proper brand assets.

- [ ] **Step 2: Commit**

```bash
git add apps/web/mandiriagro/public/ apps/web/pakerti/public/
git commit -m "chore: add placeholder public assets for mandiriagro and pakerti"
```

---

## Summary

| Task | Description | Estimated Steps |
|------|-------------|-----------------|
| 1 | Scaffold mandiriagro app skeleton | 8 |
| 2 | Add i18n and translations | 6 |
| 3 | Add company data and UI components | 3 |
| 4 | Build layouts, pages, header, footer, sections | 13 |
| 5 | Clone to pakerti and customize | 9 |
| 6 | Docker compose + deploy manifests | 4 |
| 7 | Public assets | 2 |
