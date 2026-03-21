import { Github } from "lucide-react";
import { Button } from "@/components/ui/button";

type Props = {
  onLogin: () => void;
  onSkip?: () => void;
};

export function WelcomePage({ onLogin, onSkip }: Props) {
  return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
      <div className="flex flex-col items-center gap-8 text-center px-4">
        {/* Logo / title */}
        <div className="flex flex-col items-center gap-2">
          <h1 className="text-5xl font-bold tracking-tight text-white">
            justralph.it
          </h1>
          <p className="text-lg text-zinc-300 font-medium">
            From idea to code. Automatically.
          </p>
        </div>

        {/* Subtitle */}
        <p className="text-zinc-500 text-base max-w-xs">
          Describe your project. Ralph builds it.
        </p>

        {/* Login button */}
        <div className="flex flex-col gap-3">
          <Button
            size="lg"
            className="bg-zinc-800 hover:bg-zinc-700 text-white border border-zinc-700 gap-2 px-6"
            onClick={onLogin}
          >
            <Github className="size-5" />
            Login with GitHub
          </Button>
          {onSkip && (
            <button
              onClick={onSkip}
              className="text-zinc-600 hover:text-zinc-400 text-sm transition-colors"
            >
              Continue without login
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
