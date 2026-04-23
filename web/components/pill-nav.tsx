"use client";

import { useState, useEffect } from "react";
import Image from "next/image";
import { useTheme } from "next-themes";
import { Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function PillNav() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  return (
    <div className="fixed top-6 left-1/2 z-50 -translate-x-1/2 w-fit">
      <div
        className={cn(
          "rounded-full border backdrop-blur-md shadow-sm",
          "bg-card/80 dark:bg-white/90",
          "px-3 py-2 flex items-center gap-6"
        )}
      >
        <div className="flex items-center gap-2 pl-2">
          <Image src="/logan_logo.svg" alt="Logo" width={40} height={40} className="-my-2 rounded-full" />
          <span className="text-sm font-bold tracking-tight dark:text-black">AlphaWhale</span>
        </div>
        <div className="hidden items-center gap-1 md:flex">
          <a
            href="https://github.com/hcslomeu/ai-engineering-monorepo"
            target="_blank"
            rel="noopener noreferrer"
            className="px-3 py-1 text-sm font-medium text-muted-foreground hover:text-[#f05023] dark:text-gray-500 dark:hover:text-[#f05023] transition-colors"
          >
            GitHub
          </a>
          <a
            href="https://hcslomeu.github.io/ai-engineering-monorepo/"
            target="_blank"
            rel="noopener noreferrer"
            className="px-3 py-1 text-sm font-medium text-muted-foreground hover:text-[#f05023] dark:text-gray-500 dark:hover:text-[#f05023] transition-colors"
          >
            Docs
          </a>
          <a
            href="https://github.com/hcslomeu"
            target="_blank"
            rel="noopener noreferrer"
            className="px-3 py-1 text-sm font-medium text-muted-foreground hover:text-[#f05023] dark:text-gray-500 dark:hover:text-[#f05023] transition-colors"
          >
            About me
          </a>
        </div>
        <div className="flex items-center gap-2 pr-1">
          <Button
            variant="ghost"
            size="icon"
            className="rounded-full h-8 w-8 dark:text-black dark:hover:bg-gray-100"
            onClick={() =>
              setTheme(resolvedTheme === "dark" ? "light" : "dark")
            }
          >
            {mounted && resolvedTheme === "dark" ? (
              <Sun className="h-4 w-4" />
            ) : (
              <Moon className="h-4 w-4" />
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
