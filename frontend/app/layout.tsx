import type { Metadata } from "next";
import { Geist_Mono } from "next/font/google";
import "./globals.css";

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "SpectraStruct",
  description: "Multimodal spectroscopy to molecular structure prediction",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col bg-[#050505] text-white font-mono">
        <header className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-8 py-4 bg-[#050505]/80 backdrop-blur-xl border-b border-white/[0.06]">
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 rounded-full bg-white/80" />
            <div className="text-sm font-bold tracking-[0.3em] uppercase">
              SpectraStruct
            </div>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-[10px] text-neutral-600 tracking-[0.15em] uppercase">
              DiamondHacks 2026
            </span>
          </div>
        </header>
        <main className="flex-1 pt-16">{children}</main>
      </body>
    </html>
  );
}
