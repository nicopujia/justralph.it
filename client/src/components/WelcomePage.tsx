import { useEffect, useState } from "react";
import { Sun, Moon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { API_URL } from "@/lib/config";
import type { Theme } from "@/hooks/useTheme";
import { BouncingLogo } from "./BouncingLogo";

type Props = {
  onLogin: () => void;
  onSkip?: () => void;
  theme?: Theme;
  onThemeToggle?: () => void;
};

export function WelcomePage({ onLogin, onSkip, theme, onThemeToggle }: Props) {
  const [oauthReady, setOauthReady] = useState<boolean | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/api/auth/github`)
      .then((res) => res.json())
      .then((data) => setOauthReady(!!data?.url))
      .catch(() => setOauthReady(false));
  }, []);

  return (
    <div className="min-h-screen bg-background grid-bg scanline-overlay flex items-center justify-center relative overflow-hidden">
      {/* Bouncing logo -- between grid bg (z-auto) and card (z-10) */}
      <BouncingLogo />

      {/* Theme toggle */}
      {onThemeToggle && (
        <button
          onClick={onThemeToggle}
          className="absolute top-4 right-4 z-20 text-primary hover:opacity-70 transition-opacity"
          aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          title={theme === "dark" ? "Light mode" : "Dark mode"}
        >
          {theme === "dark" ? <Sun className="size-5" /> : <Moon className="size-5" />}
        </button>
      )}

      {/* Centered container */}
      <div className="relative z-10 border-2 border-primary bg-card p-10 flex flex-col items-center gap-8 text-center min-w-[340px] max-w-sm">
        {/* Red accent square -- always red, intentional brand color */}
        <span className="absolute top-0 right-0 w-3 h-3 bg-[var(--color-error)]" aria-hidden="true" />

        {/* Title section */}
        <div className="flex flex-col items-center gap-3">
          {/* Corner bracket decoration */}
          <div className="relative px-4 py-2">
            {/* top-left bracket */}
            <span className="absolute top-0 left-0 w-3 h-3 border-t-2 border-l-2 border-primary" aria-hidden="true" />
            {/* top-right bracket */}
            <span className="absolute top-0 right-0 w-3 h-3 border-t-2 border-r-2 border-primary" aria-hidden="true" />
            {/* bottom-left bracket */}
            <span className="absolute bottom-0 left-0 w-3 h-3 border-b-2 border-l-2 border-primary" aria-hidden="true" />
            {/* bottom-right bracket */}
            <span className="absolute bottom-0 right-0 w-3 h-3 border-b-2 border-r-2 border-primary" aria-hidden="true" />
            <h1 className="glitch-text text-5xl font-bold uppercase tracking-[0.2em] text-foreground px-2">
              JUSTRALPH.IT
            </h1>
          </div>
          <p className="text-primary text-sm uppercase tracking-widest">
            FROM IDEA TO CODE
          </p>
          <p className="text-muted-foreground text-xs uppercase tracking-widest">
            DESCRIBE YOUR PROJECT. RALPH BUILDS IT.
          </p>
        </div>

        {/* Actions */}
        <div className="flex flex-col gap-3 w-full">
          <div title={oauthReady === false ? "GitHub OAuth not configured" : undefined}>
            <button
              onClick={onLogin}
              disabled={oauthReady === false}
              className={[
                "w-full border-2 bg-transparent uppercase tracking-wider text-sm py-3 px-4 transition-colors font-bold",
                oauthReady === false
                  ? "border-border text-muted-foreground cursor-not-allowed"
                  : "border-primary text-primary hover:bg-primary hover:text-primary-foreground",
              ].join(" ")}
            >
              {oauthReady === false ? "GITHUB OAUTH NOT CONFIGURED" : "LOGIN WITH GITHUB"}
            </button>
          </div>

          {onSkip && (
            <button
              onClick={onSkip}
              className="text-muted-foreground hover:text-primary text-xs uppercase tracking-wider transition-colors"
            >
              CONTINUE WITHOUT LOGIN
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
