import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Diehl VIN Platform",
  description: "VIN lookup, DTNA order tracking, history, and fleet data management.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
