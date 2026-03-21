import { type ComponentType, type ReactNode, useEffect, useMemo, useState } from "react";
import {
  ArrowUpRight,
  CreditCard,
  Github,
  ReceiptText,
  ShieldCheck,
  UserRound,
  Wallet,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { useSearchParams } from "react-router-dom";

type SettingsView = "profile" | "plan" | "usage";

const settingsTabs: Array<{ id: SettingsView; label: string }> = [
  { id: "profile", label: "Profile" },
  { id: "plan", label: "Plan" },
  { id: "usage", label: "Usage" },
];

const usageRows = [
  { project: "Northstar relaunch", tokens: "412,000", spend: "$12.36", share: "34%" },
  { project: "Atlas client portal", tokens: "365,000", spend: "$10.95", share: "30%" },
  { project: "Signal API rollout", tokens: "267,000", spend: "$8.01", share: "22%" },
  { project: "Meridian admin", tokens: "171,000", spend: "$5.13", share: "14%" },
];

export function SettingsPage() {
  const [searchParams] = useSearchParams();
  const [activeView, setActiveView] = useState<SettingsView>("profile");
  const [paymentOpen, setPaymentOpen] = useState(false);

  useEffect(() => {
    const requestedTab = searchParams.get("tab");

    if (requestedTab === "profile" || requestedTab === "plan" || requestedTab === "usage") {
      setActiveView(requestedTab);
    }
  }, [searchParams]);

  const content = useMemo(() => {
    switch (activeView) {
      case "plan":
        return <PlanView />;
      case "usage":
        return <UsageView />;
      case "profile":
      default:
        return <ProfileView paymentOpen={paymentOpen} onTogglePayment={() => setPaymentOpen(open => !open)} />;
    }
  }, [activeView, paymentOpen]);

  return (
    <section className="relative flex h-full min-h-0 overflow-auto bg-background">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(230,235,255,0.05),transparent_28%),linear-gradient(180deg,rgba(255,255,255,0.02),transparent_24%)]" />
      <div className="relative mx-auto flex w-full max-w-[1280px] flex-col gap-8 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        <div className="grid gap-4 border-b border-border pb-6 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
          <div className="grid gap-2">
            <p className="text-[11px] uppercase tracking-[0.18em] text-[color:var(--text-muted)]">Settings</p>
            <h1 className="font-serif-ui text-4xl tracking-[-0.05em] text-foreground sm:text-5xl">Account control surface.</h1>
            <p className="max-w-2xl text-sm leading-7 text-[color:var(--text-secondary)] sm:text-base">
              Review identity, billing posture, and usage from one quiet workspace. Keep ownership visible before execution scales.
            </p>
          </div>

          <div className="inline-flex w-full max-w-full rounded-[var(--radius-sm)] border border-border bg-[rgba(255,255,255,0.02)] p-1 lg:w-auto">
            {settingsTabs.map(tab => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveView(tab.id)}
                className={cn(
                  "flex-1 rounded-[4px] px-4 py-2.5 text-sm transition-colors lg:flex-none",
                  activeView === tab.id
                    ? "bg-panel text-foreground"
                    : "text-[color:var(--text-muted)] hover:text-[color:var(--text-secondary)]",
                )}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {content}
      </div>
    </section>
  );
}

function SettingsSection({
  eyebrow,
  title,
  description,
  action,
  children,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <Card className="gap-0 rounded-[var(--radius-md)] bg-[rgba(12,12,13,0.86)] py-0">
      <CardHeader className="gap-3 border-b border-border px-6 py-6 sm:px-8">
        <div className="grid gap-2">
          <p className="text-[11px] uppercase tracking-[0.18em] text-[color:var(--text-muted)]">{eyebrow}</p>
          <CardTitle className="text-[1.45rem] tracking-[-0.03em] text-foreground">{title}</CardTitle>
          <CardDescription className="max-w-2xl text-sm leading-7">{description}</CardDescription>
        </div>
        {action ? <div className="pt-1">{action}</div> : null}
      </CardHeader>
      <CardContent className="px-6 py-6 sm:px-8 sm:py-7">{children}</CardContent>
    </Card>
  );
}

function ProfileView({ paymentOpen, onTogglePayment }: { paymentOpen: boolean; onTogglePayment: () => void }) {
  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1.3fr)_minmax(320px,0.7fr)]">
      <div className="grid gap-6">
        <SettingsSection
          eyebrow="Identity"
          title="Operator profile"
          description="Use the profile entry in the top utility bar to reach settings. Keep personal and account ownership explicit before GitHub and billing actions expand."
        >
          <div className="grid gap-6 md:grid-cols-[160px_minmax(0,1fr)] md:items-start">
            <div className="flex h-32 w-32 items-center justify-center rounded-[var(--radius-md)] border border-border bg-[linear-gradient(180deg,rgba(255,255,255,0.06),rgba(255,255,255,0.02))] text-3xl text-foreground">
              TL
            </div>
            <div className="grid gap-5">
              <div className="grid gap-2">
                <Label htmlFor="operator-name">Display name</Label>
                <Input id="operator-name" defaultValue="Tomy Leone" />
              </div>
              <div className="grid gap-2 sm:grid-cols-2 sm:gap-4">
                <div className="grid gap-2">
                  <Label htmlFor="operator-email">Email</Label>
                  <Input id="operator-email" defaultValue="tomileonel18@gmail.com" />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="operator-role">Role</Label>
                  <Input id="operator-role" defaultValue="Owner / Operator" />
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-3 border-t border-border pt-4">
                <Button>Save profile</Button>
                <Button variant="ghost">Upload avatar</Button>
              </div>
            </div>
          </div>
        </SettingsSection>

        <SettingsSection
          eyebrow="Connections"
          title="GitHub identity"
          description="Repository access should stay attached to one clear human identity. Connected status and scope remain visible without adding extra chrome."
          action={<StatusBadge icon={ShieldCheck} label="Connected" tone="success" />}
        >
          <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
            <div className="flex items-start gap-4">
              <div className="flex size-12 items-center justify-center rounded-full border border-border bg-panel">
                <Github className="size-5 text-foreground" />
              </div>
              <div className="grid gap-1">
                <p className="text-sm text-foreground">@tomyleone</p>
                <p className="text-sm leading-7 text-[color:var(--text-secondary)]">
                  Primary GitHub identity for repository sync, branch creation, and pull request actions.
                </p>
              </div>
            </div>
            <div className="flex flex-wrap gap-3">
              <Button variant="secondary">
                View GitHub
                <ArrowUpRight className="size-4" />
              </Button>
              <Button variant="ghost">Refresh access</Button>
            </div>
          </div>
        </SettingsSection>

        <SettingsSection
          eyebrow="Billing"
          title="Payment ownership"
          description="Billing control stays in the account layer, not inside project screens. Use a dedicated management view when payment details need review or action."
          action={
            <Button variant={paymentOpen ? "secondary" : "default"} onClick={onTogglePayment}>
              {paymentOpen ? "Hide payment view" : "Manage payment"}
            </Button>
          }
        >
          <div className="grid gap-4">
            <div className="grid gap-4 md:grid-cols-3">
              <MetricBlock icon={Wallet} label="Billing owner" value="Tomy Leone" detail="Primary account holder" />
              <MetricBlock icon={CreditCard} label="Default method" value="Visa ending 2048" detail="Expires 09/28" />
              <MetricBlock icon={ReceiptText} label="Next charge" value="Apr 1, 2026" detail="$120.32 projected" />
            </div>

            {paymentOpen ? (
              <div className="grid gap-6 rounded-[var(--radius-md)] border border-border bg-[rgba(255,255,255,0.02)] p-5 sm:p-6 lg:grid-cols-[minmax(0,1fr)_320px]">
                <div className="grid gap-5">
                  <div className="grid gap-2">
                    <p className="text-[11px] uppercase tracking-[0.18em] text-[color:var(--text-muted)]">Payment view</p>
                    <h3 className="text-xl tracking-[-0.03em] text-foreground">Manage billing method and invoices.</h3>
                    <p className="text-sm leading-7 text-[color:var(--text-secondary)]">
                      Keep the payment method valid, preserve invoice visibility, and make ownership transfer explicit before the account changes hands.
                    </p>
                  </div>

                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="grid gap-2">
                      <Label htmlFor="cardholder">Cardholder name</Label>
                      <Input id="cardholder" defaultValue="Tomy Leone" />
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="billing-email">Billing email</Label>
                      <Input id="billing-email" defaultValue="billing@justralph.it" />
                    </div>
                    <div className="grid gap-2 sm:col-span-2">
                      <Label htmlFor="billing-address">Billing address</Label>
                      <Input id="billing-address" defaultValue="72 Mercer St, New York, NY 10012" />
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-3 border-t border-border pt-4">
                    <Button>Update payment method</Button>
                    <Button variant="secondary">Download latest invoice</Button>
                    <Button variant="ghost">Transfer billing owner</Button>
                  </div>
                </div>

                <div className="grid gap-4 rounded-[var(--radius-md)] border border-border bg-[rgba(0,0,0,0.16)] p-5">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-[color:var(--text-muted)]">Current setup</p>
                  <div className="grid gap-3 border-b border-border pb-4">
                    <p className="text-sm text-foreground">Visa ending 2048</p>
                    <p className="text-sm text-[color:var(--text-secondary)]">Autopay enabled for monthly base, project overages, and token usage.</p>
                  </div>
                  <div className="grid gap-3 text-sm text-[color:var(--text-secondary)]">
                    <div className="flex items-center justify-between gap-4">
                      <span>Tax profile</span>
                      <span className="text-foreground">US business</span>
                    </div>
                    <div className="flex items-center justify-between gap-4">
                      <span>Invoice cycle</span>
                      <span className="text-foreground">Monthly</span>
                    </div>
                    <div className="flex items-center justify-between gap-4">
                      <span>Statement date</span>
                      <span className="text-foreground">Day 1</span>
                    </div>
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        </SettingsSection>
      </div>

      <div className="grid gap-6">
        <Card className="rounded-[var(--radius-md)] bg-[rgba(12,12,13,0.86)] py-0">
          <CardHeader className="border-b border-border px-6 py-6">
            <p className="text-[11px] uppercase tracking-[0.18em] text-[color:var(--text-muted)]">Access</p>
            <CardTitle className="text-xl tracking-[-0.03em]">Account posture</CardTitle>
            <CardDescription className="leading-7">A quick read on account trust, connectivity, and active financial ownership.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 px-6 py-6">
            <MiniStatus label="Profile status" value="Verified" tone="success" />
            <MiniStatus label="GitHub scope" value="Repo + PR access" tone="neutral" />
            <MiniStatus label="Payment state" value="Autopay active" tone="success" />
          </CardContent>
        </Card>

        <Card className="rounded-[var(--radius-md)] bg-[rgba(12,12,13,0.86)] py-0">
          <CardHeader className="border-b border-border px-6 py-6">
            <p className="text-[11px] uppercase tracking-[0.18em] text-[color:var(--text-muted)]">Notes</p>
            <CardTitle className="text-xl tracking-[-0.03em]">Operational guidance</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 px-6 py-6 text-sm leading-7 text-[color:var(--text-secondary)]">
            <p>Keep GitHub and billing ownership attached to one accountable operator.</p>
            <p>Review payment details before expanding project count or usage ceilings.</p>
            <p>Use the usage view to monitor token drift before it turns into surprise spend.</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function PlanView() {
  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
      <SettingsSection
        eyebrow="Plan"
        title="Pricing model"
        description="Pricing stays explicit and operational. One calm card explains the base platform fee, project expansion cost, and token usage rate."
      >
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_280px] lg:items-start">
          <div className="grid gap-5">
            <div className="grid gap-2">
              <p className="text-[11px] uppercase tracking-[0.18em] text-[color:var(--text-muted)]">Included structure</p>
              <h3 className="text-xl tracking-[-0.03em] text-foreground">One account with clear usage economics.</h3>
              <p className="max-w-2xl text-sm leading-7 text-[color:var(--text-secondary)]">
                The base fee keeps the workspace active, project fees scale with active execution lanes, and token pricing stays visible so teams can forecast before usage spikes.
              </p>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <MetricBlock icon={Wallet} label="Base platform" value="$50/mo" detail="Account access and control surface" />
              <MetricBlock icon={UserRound} label="Per project" value="+$10/mo" detail="Each active project workspace" />
              <MetricBlock icon={ReceiptText} label="Token usage" value="+$30" detail="Per million tokens" />
            </div>
          </div>

          <div className="rounded-[var(--radius-md)] border border-border bg-[linear-gradient(180deg,rgba(255,255,255,0.05),rgba(255,255,255,0.02))] p-6">
            <div className="grid gap-3 border-b border-border pb-5">
              <p className="text-[11px] uppercase tracking-[0.18em] text-[color:var(--text-muted)]">Current plan</p>
              <p className="font-serif-ui text-5xl tracking-[-0.05em] text-foreground">Pro</p>
              <p className="text-sm leading-7 text-[color:var(--text-secondary)]">Built for agencies and small teams that need a stable AI execution environment.</p>
            </div>
            <div className="grid gap-3 py-5 text-sm text-[color:var(--text-secondary)]">
              <PriceLine label="$50/mo base" />
              <PriceLine label="+ $10/mo per project" />
              <PriceLine label="+ $30 per million tokens" />
            </div>
            <Button className="w-full">Manage plan</Button>
          </div>
        </div>
      </SettingsSection>

      <Card className="rounded-[var(--radius-md)] bg-[rgba(12,12,13,0.86)] py-0">
        <CardHeader className="border-b border-border px-6 py-6">
          <p className="text-[11px] uppercase tracking-[0.18em] text-[color:var(--text-muted)]">Forecast</p>
          <CardTitle className="text-xl tracking-[-0.03em]">Estimated monthly bill</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 px-6 py-6">
          <ForecastLine label="Base" value="$50.00" />
          <ForecastLine label="4 active projects" value="$40.00" />
          <ForecastLine label="1.21M tokens" value="$36.45" />
        </CardContent>
        <CardFooter className="justify-between border-t border-border px-6 py-5 text-sm text-[color:var(--text-secondary)]">
          <span>Total</span>
          <span className="text-foreground">$126.45</span>
        </CardFooter>
      </Card>
    </div>
  );
}

function UsageView() {
  return (
    <div className="grid gap-6">
      <SettingsSection
        eyebrow="Usage"
        title="Token consumption"
        description="Monitor current billing-cycle usage before token volume turns into unplanned spend. The view stays quiet, but the cost signals remain explicit."
      >
        <div className="grid gap-4 xl:grid-cols-4">
          <MetricBlock icon={ReceiptText} label="Current cycle" value="1.21M" detail="Mar 1 to Mar 31" />
          <MetricBlock icon={Wallet} label="Estimated spend" value="$36.45" detail="Token usage only" />
          <MetricBlock icon={UserRound} label="Active projects" value="4" detail="Usage-producing workspaces" />
          <MetricBlock icon={ShieldCheck} label="Reset date" value="Apr 1" detail="Billing cycle renews" />
        </div>
      </SettingsSection>

      <Card className="rounded-[var(--radius-md)] bg-[rgba(12,12,13,0.86)] py-0">
        <CardHeader className="border-b border-border px-6 py-6 sm:px-8">
          <p className="text-[11px] uppercase tracking-[0.18em] text-[color:var(--text-muted)]">Breakdown</p>
          <CardTitle className="text-[1.45rem] tracking-[-0.03em]">Usage by project</CardTitle>
          <CardDescription className="max-w-2xl text-sm leading-7">Each active workspace contributes to the current cycle. Review the mix before opening more execution lanes.</CardDescription>
        </CardHeader>
        <CardContent className="px-0 py-0">
          <div className="overflow-x-auto">
            <table className="min-w-full border-separate border-spacing-0 text-left text-sm">
              <thead>
                <tr className="text-[11px] uppercase tracking-[0.16em] text-[color:var(--text-muted)]">
                  <th className="border-b border-border px-6 py-4 font-medium sm:px-8">Project</th>
                  <th className="border-b border-border px-6 py-4 font-medium">Tokens</th>
                  <th className="border-b border-border px-6 py-4 font-medium">Spend</th>
                  <th className="border-b border-border px-6 py-4 font-medium sm:px-8">Share</th>
                </tr>
              </thead>
              <tbody>
                {usageRows.map(row => (
                  <tr key={row.project} className="text-[color:var(--text-secondary)]">
                    <td className="border-b border-border px-6 py-4 text-foreground last:border-b-0 sm:px-8">{row.project}</td>
                    <td className="border-b border-border px-6 py-4 last:border-b-0">{row.tokens}</td>
                    <td className="border-b border-border px-6 py-4 last:border-b-0">{row.spend}</td>
                    <td className="border-b border-border px-6 py-4 last:border-b-0 sm:px-8">{row.share}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function MetricBlock({
  icon: Icon,
  label,
  value,
  detail,
}: {
  icon: ComponentType<{ className?: string }>;
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="grid gap-3 rounded-[var(--radius-md)] border border-border bg-[rgba(255,255,255,0.02)] p-5">
      <div className="flex size-10 items-center justify-center rounded-[var(--radius-sm)] border border-border bg-panel">
        <Icon className="size-4 text-[color:var(--text-secondary)]" />
      </div>
      <div className="grid gap-1">
        <p className="text-[11px] uppercase tracking-[0.16em] text-[color:var(--text-muted)]">{label}</p>
        <p className="text-lg tracking-[-0.03em] text-foreground">{value}</p>
        <p className="text-sm leading-6 text-[color:var(--text-secondary)]">{detail}</p>
      </div>
    </div>
  );
}

function PriceLine({ label }: { label: string }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-border pb-3 last:border-b-0 last:pb-0">
      <span>{label}</span>
      <span className="text-foreground">Included</span>
    </div>
  );
}

function ForecastLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 text-sm text-[color:var(--text-secondary)]">
      <span>{label}</span>
      <span className="text-foreground">{value}</span>
    </div>
  );
}

function StatusBadge({
  icon: Icon,
  label,
  tone,
}: {
  icon: ComponentType<{ className?: string }>;
  label: string;
  tone: "success" | "neutral";
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-full border px-3 py-2 text-[11px] uppercase tracking-[0.14em]",
        tone === "success"
          ? "border-[rgba(155,199,154,0.4)] bg-[rgba(155,199,154,0.08)] text-[color:var(--success)]"
          : "border-border bg-[rgba(255,255,255,0.03)] text-[color:var(--text-secondary)]",
      )}
    >
      <Icon className="size-3.5" />
      {label}
    </span>
  );
}

function MiniStatus({ label, value, tone }: { label: string; value: string; tone: "success" | "neutral" }) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-[var(--radius-sm)] border border-border bg-[rgba(255,255,255,0.02)] px-4 py-3">
      <span className="text-sm text-[color:var(--text-secondary)]">{label}</span>
      <StatusBadge icon={tone === "success" ? ShieldCheck : UserRound} label={value} tone={tone} />
    </div>
  );
}
