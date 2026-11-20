import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";

import { Sidebar } from "@/components/Sidebar";
import { THEME_INIT_SCRIPT } from "@/components/ThemeToggle";

import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono-face" });

export const metadata: Metadata = {
  title: { default: "vectora-bio", template: "%s · vectora-bio" },
  description:
    "Phenotypic drug discovery on Cell Painting: rank look-alike compounds, candidate targets, likely mechanisms and genetic rescuers.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${mono.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="min-h-screen font-sans antialiased">
        <div className="flex min-h-screen flex-col md:flex-row">
          <Sidebar />
          <main className="min-w-0 flex-1 px-5 pt-8 pb-24 sm:px-8 md:px-12 md:pt-12">
            <div className="mx-auto max-w-[1200px]">{children}</div>
          </main>
        </div>
      </body>
    </html>
  );
}
