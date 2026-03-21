import { useEffect, useState } from "react";
import { Sun, Moon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { API_URL } from "@/lib/config";
import type { Theme } from "@/hooks/useTheme";

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
    <div className="min-h-screen bg-[#f5f5f0] dark:bg-black grid-bg scanline-overlay flex items-center justify-center relative">
      {/* Theme toggle */}
      {onThemeToggle && (
        <button
          onClick={onThemeToggle}
          className="absolute top-4 right-4 text-[#00AA33] dark:text-[#00FF41] hover:opacity-70 transition-opacity"
          aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          title={theme === "dark" ? "Light mode" : "Dark mode"}
        >
          {theme === "dark" ? <Sun className="size-5" /> : <Moon className="size-5" />}
        </button>
      )}

      {/* Centered container */}
      <div className="relative border-2 border-[#00AA33] dark:border-[#00FF41] bg-white dark:bg-[#0a0a0a] p-10 flex flex-col items-center gap-8 text-center min-w-[340px] max-w-sm">
        {/* Red accent square */}
        <span className="absolute top-0 right-0 w-3 h-3 bg-[#FF0033]" aria-hidden="true" />

        {/* Title section */}
        <div className="flex flex-col items-center gap-3">
          {/* Corner bracket decoration */}
          <div className="relative px-4 py-2">
            {/* top-left bracket */}
            <span className="absolute top-0 left-0 w-3 h-3 border-t-2 border-l-2 border-[#00AA33] dark:border-[#00FF41]" aria-hidden="true" />
            {/* top-right bracket */}
            <span className="absolute top-0 right-0 w-3 h-3 border-t-2 border-r-2 border-[#00AA33] dark:border-[#00FF41]" aria-hidden="true" />
            {/* bottom-left bracket */}
            <span className="absolute bottom-0 left-0 w-3 h-3 border-b-2 border-l-2 border-[#00AA33] dark:border-[#00FF41]" aria-hidden="true" />
            {/* bottom-right bracket */}
            <span className="absolute bottom-0 right-0 w-3 h-3 border-b-2 border-r-2 border-[#00AA33] dark:border-[#00FF41]" aria-hidden="true" />
            <h1 className="glitch-text text-5xl font-bold uppercase tracking-[0.2em] text-black dark:text-white px-2">
              JUSTRALPH.IT
            </h1>
          </div>
          <p className="text-[#00AA33] dark:text-[#00FF41] text-sm uppercase tracking-widest">
            FROM IDEA TO CODE
          </p>
          <p className="text-[#555] dark:text-[#333] text-xs uppercase tracking-widest">
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
                  ? "border-[#555] dark:border-[#333] text-[#555] dark:text-[#333] cursor-not-allowed"
                  : "border-[#00AA33] dark:border-[#00FF41] text-[#00AA33] dark:text-[#00FF41] hover:bg-[#00AA33] dark:hover:bg-[#00FF41] hover:text-black",
              ].join(" ")}
            >
              {oauthReady === false ? "GITHUB OAUTH NOT CONFIGURED" : "LOGIN WITH GITHUB"}
            </button>
          </div>

          {onSkip && (
            <button
              onClick={onSkip}
              className="text-[#555] dark:text-[#333] hover:text-[#00AA33] dark:hover:text-[#00FF41] text-xs uppercase tracking-wider transition-colors"
            >
              CONTINUE WITHOUT LOGIN
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
