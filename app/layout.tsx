import type { Metadata } from "next";
import "./globals.css";
import { TopTabs } from "../components/top-tabs";

export const metadata: Metadata = {
  title: "Diehl VIN Platform",
  description: "VIN In-Service, DTNA order tracking, and Excel-first worker automation.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <TopTabs />
        {children}
      </body>
    </html>
  );
}
