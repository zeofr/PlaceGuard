import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PlaceGuard — Ramaiah Institute of Technology",
  description: "Official placement information and eligibility management portal for RIT students",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
