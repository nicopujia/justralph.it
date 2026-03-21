import { Github } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";

export function LandingPage() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="grid min-h-screen lg:grid-cols-[1fr_0.95fr]">
        <section className="relative overflow-hidden border-b border-border lg:border-r lg:border-b-0">
          <div
            className="absolute inset-0"
            aria-hidden="true"
            style={{
              backgroundImage:
                "radial-gradient(circle at 72% 18%, rgba(255,255,255,0.38), transparent 27%), radial-gradient(circle at 62% 52%, rgba(255,255,255,0.12), transparent 22%), radial-gradient(circle at 66% 76%, rgba(255,255,255,0.2), transparent 28%), linear-gradient(180deg, rgba(0,0,0,0.56) 0%, rgba(0,0,0,0.1) 100%), linear-gradient(90deg, #0b0b0b 0%, #111111 26%, #5f5f5f 100%)",
              filter: "grayscale(1)",
            }}
          />
          <div
            className="absolute inset-0 opacity-[0.18]"
            aria-hidden="true"
            style={{
              backgroundImage: "radial-gradient(circle at center, rgba(255,255,255,0.08) 0%, transparent 55%)",
              mixBlendMode: "soft-light",
            }}
          />

          <div className="relative flex min-h-[52vh] items-center justify-center px-8 py-14 md:px-12 lg:min-h-screen lg:px-16">
            <div className="grid max-w-[430px] gap-6 text-center">
              <p className="font-serif-ui text-[2.2rem] leading-[1.35] tracking-[-0.04em] text-white md:text-[3.15rem] md:leading-[1.28]">
                Without clear requirements, the loop will ship contradictions before it ships results.
              </p>
              <p className="text-sm text-[rgba(243,242,238,0.58)]">justralph.it</p>
            </div>
          </div>
        </section>

        <section className="flex min-h-[48vh] items-center justify-center px-8 py-14 md:px-12 lg:min-h-screen lg:px-16">
          <div className="w-full max-w-[416px]">
            <div className="grid gap-8">
              <div className="grid gap-3">
                <h1 className="font-serif-ui text-[2.2rem] tracking-[-0.05em] text-foreground md:text-[2.6rem]">
                  Welcome to justralph.it
                </h1>
                <p className="text-sm text-[color:var(--text-secondary)]">Continue with GitHub to enter the workspace</p>
              </div>

              <div className="grid gap-3">
                <Button asChild size="lg" variant="outline" className="h-12 w-full justify-center bg-transparent text-foreground hover:bg-[rgba(255,255,255,0.02)]">
                  <Link to="/app">
                    <Github className="size-4" />
                    Continue with GitHub
                  </Link>
                </Button>
              </div>

              <p className="pt-20 text-center text-sm leading-7 text-[color:var(--text-muted)] md:pt-28">
                By signing in you agree to our <a href="#" className="text-[color:var(--text-secondary)] underline underline-offset-4">Terms of service</a> and <a href="#" className="text-[color:var(--text-secondary)] underline underline-offset-4">Privacy policy</a>.
              </p>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
