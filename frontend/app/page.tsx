"use client";

import Sidebar from "@/components/Sidebar";
import Chat from "@/components/Chat";

export default function Home() {
  return (
    <div className="flex h-screen w-full bg-background text-text overflow-hidden">
      <Sidebar />
      <main className="flex-1 flex flex-col min-w-0 bg-background">
        <Chat />
      </main>
    </div>
  );
}