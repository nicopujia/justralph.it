import { useEffect, useState } from "react";
import { Github, Sun, Moon } from "lucide-react";
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
  // Check if GitHub OAuth is configured by probing the auth endpoint
  const [oauthReady, setOauthReady] = useState<boolean | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/api/auth/github`)
      .then((res) => res.json())
      .then((data) => setOauthReady(!!data?.url))
      .catch(() => setOauthReady(false));
  }, []);

  return (
    <div className="min-h-screen dark:bg-zinc-950 bg-white flex items-center justify-center relative">
      {/* Theme toggle - top right corner */}
      {onThemeToggle && (
        <Button
          variant="ghost"
          size="icon"
          onClick={onThemeToggle}
          className="absolute top-4 right-4 dark:text-zinc-400 text-gray-500 dark:hover:text-zinc-200 hover:text-gray-700"
          aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          title={theme === "dark" ? "Light mode" : "Dark mode"}
        >
          {theme === "dark" ? <Sun className="size-5" /> : <Moon className="size-5" />}
        </Button>
      )}
      {/* Animated gradient border wrapper */}
      <div className="relative p-px rounded-2xl animated-border">
        <div className="relative rounded-2xl dark:bg-zinc-900 bg-gray-50 px-10 py-12 flex flex-col items-center gap-8 text-center min-w-[340px] max-w-sm">
          {/* Brand */}
          <div className="flex flex-col items-center gap-2">
            <h1 className="text-5xl font-mono font-bold tracking-tight dark:text-zinc-100 text-gray-900">
              justralph.it
            </h1>
            <p className="text-base dark:text-zinc-400 text-gray-500 font-medium">
              From idea to code. Automatically.
            </p>
          </div>

          {/* Tagline */}
          <p className="dark:text-zinc-500 text-gray-400 text-sm max-w-xs">
            Describe your project. Ralph builds it.
          </p>

          {/* Actions */}
          <div className="flex flex-col gap-3 w-full">
            {/* GitHub login button */}
            <div title={oauthReady === false ? "GitHub OAuth not configured" : undefined}>
              <Button
                size="lg"
                className="w-full dark:bg-zinc-800 dark:hover:bg-zinc-700 bg-gray-900 hover:bg-gray-800 dark:text-zinc-100 text-white dark:border-zinc-700 border-gray-700 border gap-2"
                onClick={onLogin}
                disabled={oauthReady === false}
              >
                <Github className="size-5" />
                {oauthReady === false ? "GitHub OAuth not configured" : "Login with GitHub"}
              </Button>
            </div>

            {onSkip && (
              <button
                onClick={onSkip}
                className="dark:text-zinc-500 text-gray-400 dark:hover:text-zinc-300 hover:text-gray-600 text-sm transition-colors"
              >
                Continue without login
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
