import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Agentic RAG",
  description: "Multi-agent retrieval-augmented generation system",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
