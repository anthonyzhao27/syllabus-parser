import type { Metadata } from "next";
import Script from "next/script";
import { Providers } from "@/components/providers";
import { Footer } from "@/components/footer";
import "./globals.css";

export const metadata: Metadata = {
  title: "Syllabuddy",
  description: "Extract assignments and due dates from your course syllabi",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased flex min-h-screen flex-col">
        <Providers>
          <div className="flex-1">{children}</div>
        </Providers>
        <Footer />
        <Script
          src="https://accounts.google.com/gsi/client"
          strategy="beforeInteractive"
        />
      </body>
    </html>
  );
}
