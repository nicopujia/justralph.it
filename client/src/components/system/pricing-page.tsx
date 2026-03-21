import { CreditCard, FolderKanban, ReceiptText } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";

const pricingRows = [
  { label: "Base platform", value: "$50/mo", detail: "Account access and control surface" },
  { label: "Per project", value: "+$10/mo", detail: "Each active project workspace" },
  { label: "Token usage", value: "+$30", detail: "Per million tokens" },
];

export function PricingPage() {
  return (
    <section className="relative flex h-full min-h-0 overflow-auto bg-background">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(230,235,255,0.05),transparent_28%),linear-gradient(180deg,rgba(255,255,255,0.02),transparent_24%)]" />
      <div className="relative mx-auto flex w-full max-w-[1180px] flex-col gap-8 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        <div className="grid gap-2 border-b border-border pb-6">
          <p className="text-[11px] uppercase tracking-[0.18em] text-[color:var(--text-muted)]">Pricing</p>
          <h1 className="font-serif-ui text-4xl tracking-[-0.05em] text-foreground sm:text-5xl">Quiet pricing, explicit cost.</h1>
          <p className="max-w-2xl text-sm leading-7 text-[color:var(--text-secondary)] sm:text-base">
            One base platform fee, predictable project expansion, and visible token pricing. Built for teams that want cost clarity before execution scales.
          </p>
        </div>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
          <Card className="rounded-[var(--radius-md)] bg-[rgba(12,12,13,0.86)] py-0">
            <CardHeader className="border-b border-border px-6 py-6 sm:px-8">
              <p className="text-[11px] uppercase tracking-[0.18em] text-[color:var(--text-muted)]">Plan</p>
              <CardTitle className="text-[1.45rem] tracking-[-0.03em] text-foreground">Pro</CardTitle>
              <CardDescription className="max-w-2xl text-sm leading-7">
                Built for agencies and small teams that need a stable AI execution environment.
              </CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 px-6 py-6 sm:px-8 sm:py-7">
              {pricingRows.map(row => (
                <div key={row.label} className="flex items-start justify-between gap-5 rounded-[var(--radius-sm)] border border-border bg-[rgba(255,255,255,0.02)] px-4 py-4">
                  <div className="grid gap-1">
                    <p className="text-sm text-foreground">{row.label}</p>
                    <p className="text-sm text-[color:var(--text-secondary)]">{row.detail}</p>
                  </div>
                  <span className="text-sm text-foreground">{row.value}</span>
                </div>
              ))}
            </CardContent>
            <CardFooter className="border-t border-border px-6 py-5 sm:px-8">
              <Button>Manage plan</Button>
            </CardFooter>
          </Card>

          <div className="grid gap-6">
            <Metric icon={CreditCard} label="Base platform" value="$50/mo" detail="Account access and ownership controls" />
            <Metric icon={FolderKanban} label="Active projects" value="+$10/mo" detail="Per active project workspace" />
            <Metric icon={ReceiptText} label="Tokens" value="+$30" detail="Per million tokens processed" />
          </div>
        </div>
      </div>
    </section>
  );
}

function Metric({
  icon: Icon,
  label,
  value,
  detail,
}: {
  icon: typeof CreditCard;
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <Card className="rounded-[var(--radius-md)] bg-[rgba(12,12,13,0.86)] py-0">
      <CardContent className="grid gap-4 px-6 py-6">
        <div className="flex size-10 items-center justify-center rounded-[var(--radius-sm)] border border-border bg-panel">
          <Icon className="size-4 text-[color:var(--text-secondary)]" />
        </div>
        <div className="grid gap-1">
          <p className="text-[11px] uppercase tracking-[0.16em] text-[color:var(--text-muted)]">{label}</p>
          <p className="text-lg tracking-[-0.03em] text-foreground">{value}</p>
          <p className="text-sm leading-6 text-[color:var(--text-secondary)]">{detail}</p>
        </div>
      </CardContent>
    </Card>
  );
}
