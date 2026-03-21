import { Github, Hammer } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

import { currentPlan } from "@/components/system/app-data";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

function HammerMark() {
  return (
    <div className="flex size-10 items-center justify-center rounded-[var(--radius-sm)] border border-border bg-[linear-gradient(180deg,rgba(255,255,255,0.05),rgba(255,255,255,0.01))] transition-colors duration-150 hover:bg-[linear-gradient(180deg,rgba(255,255,255,0.1),rgba(255,255,255,0.03))]">
      <Hammer className="size-4 text-foreground" />
    </div>
  );
}

export function AppShell() {
  return (
    <div className="h-screen overflow-hidden bg-background text-foreground">
      <header className="sticky top-0 z-30 border-b border-border bg-[rgba(10,10,10,0.92)] backdrop-blur-md">
        <div className="mx-auto flex min-h-16 w-full items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
          <div className="flex min-w-0 items-center gap-4">
            <NavLink to="/app/projects" className="flex items-center gap-3">
              <HammerMark />
            </NavLink>
          </div>

          <div className="flex items-center gap-3">
            <Button asChild variant="secondary" size="sm" className="h-9 px-3 text-foreground">
              <NavLink to="/app/settings?tab=plan">{currentPlan}</NavLink>
            </Button>
            <NavLink
              to="/app/settings"
              aria-label="GitHub profile"
              className={({ isActive }) =>
                cn(
                  "flex size-10 items-center justify-center rounded-full border border-border bg-panel text-foreground transition-colors hover:bg-[rgba(255,255,255,0.04)]",
                  isActive && "border-[color:var(--accent-primary)] bg-[rgba(199,210,254,0.08)]",
                )
              }
            >
              <Github className="size-4" />
            </NavLink>
          </div>
        </div>
      </header>

      <main className="h-[calc(100vh-64px)] overflow-hidden">
        <Outlet />
      </main>
    </div>
  );
}
