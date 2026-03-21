import {
  Bell,
  Bot,
  BriefcaseBusiness,
  Check,
  ChevronRight,
  CircleDot,
  Clock3,
  Command,
  CreditCard,
  FolderKanban,
  LayoutGrid,
  MessageSquareText,
  PanelLeft,
  Plus,
  Search,
  Settings,
  Sparkles,
  TerminalSquare,
} from "lucide-react";
import type { ComponentProps, ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

type SectionProps = {
  eyebrow: string;
  title: string;
  description: string;
  children: ReactNode;
};

function Section({ eyebrow, title, description, children }: SectionProps) {
  return (
    <section className="grid gap-6 rounded-[var(--radius-lg)] border border-border bg-[rgba(255,255,255,0.02)] p-5 md:p-8">
      <div className="grid gap-3 border-b border-border pb-6 md:grid-cols-[minmax(0,280px)_1fr] md:items-start md:gap-8">
        <div className="grid gap-3">
          <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-[color:var(--text-muted)]">{eyebrow}</p>
          <div className="grid gap-2">
            <h2 className="text-2xl font-medium tracking-[-0.04em] text-foreground md:text-[2rem]">{title}</h2>
            <p className="max-w-xl text-sm leading-7 text-[color:var(--text-secondary)] md:text-[15px]">{description}</p>
          </div>
        </div>
        <div>{children}</div>
      </div>
    </section>
  );
}

function Surface({ className, ...props }: ComponentProps<"div">) {
  return <div className={cn("surface-panel rounded-[var(--radius-lg)]", className)} {...props} />;
}

function SmallStat({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <Surface className="grid gap-6 p-6">
      <div className="grid gap-3">
        <div className="font-serif-ui text-4xl tracking-[-0.04em] text-foreground">{value}</div>
        <div className="grid gap-1">
          <p className="text-sm text-foreground">{label}</p>
          <p className="text-sm text-[color:var(--text-muted)]">{detail}</p>
        </div>
      </div>
    </Surface>
  );
}

function SearchBar() {
  return (
    <div className="flex h-11 items-center gap-3 rounded-[var(--radius-sm)] border border-border bg-[rgba(255,255,255,0.02)] px-4 text-sm text-[color:var(--text-secondary)]">
      <Search className="size-4 text-[color:var(--text-muted)]" />
      <span>Find sessions, prompts, and blocked steps</span>
    </div>
  );
}

function SegmentedControl() {
  return (
    <div className="inline-flex rounded-[var(--radius-sm)] border border-border bg-[rgba(255,255,255,0.02)] p-1">
      <button className="rounded-[4px] bg-panel-2 px-3 py-2 text-sm text-foreground">Execution</button>
      <button className="rounded-[4px] px-3 py-2 text-sm text-[color:var(--text-muted)]">Review</button>
      <button className="rounded-[4px] px-3 py-2 text-sm text-[color:var(--text-muted)]">Memory</button>
    </div>
  );
}

function TabBar() {
  const tabs = ["General", "Billing", "Projects", "Notifications", "Developer"];
  return (
    <div className="flex flex-wrap gap-5 border-b border-border pb-3">
      {tabs.map((tab, index) => (
        <button
          key={tab}
          className={cn(
            "pb-2 text-sm tracking-[-0.01em] transition-colors",
            index === 0 ? "border-b border-foreground text-foreground" : "text-[color:var(--text-muted)] hover:text-[color:var(--text-secondary)]",
          )}
        >
          {tab}
        </button>
      ))}
    </div>
  );
}

function SideRail() {
  const items = [LayoutGrid, MessageSquareText, FolderKanban, TerminalSquare, CreditCard, Settings];

  return (
    <div className="flex h-full min-h-[620px] w-[76px] flex-col justify-between border-r border-border bg-[rgba(255,255,255,0.01)] px-3 py-4">
      <div className="grid gap-3">
        <div className="flex size-10 items-center justify-center rounded-full border border-border bg-panel">
          <Sparkles className="size-4 text-foreground" />
        </div>
        <div className="grid gap-2 pt-3">
          {items.map((Icon, index) => (
            <button
              key={index}
              className={cn(
                "flex size-10 items-center justify-center rounded-[var(--radius-sm)] border border-transparent text-[color:var(--text-muted)] transition-colors hover:border-border hover:bg-[rgba(255,255,255,0.03)] hover:text-foreground",
                index === 1 && "border-border bg-panel text-foreground",
              )}
            >
              <Icon className="size-4" />
            </button>
          ))}
        </div>
      </div>
      <button className="flex size-10 items-center justify-center rounded-[var(--radius-sm)] border border-border bg-panel text-sm text-foreground">
        JR
      </button>
    </div>
  );
}

function TopBar() {
  return (
    <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border px-5 py-4">
      <div className="min-w-[240px] flex-1 max-w-[720px]">
        <SearchBar />
      </div>
      <div className="flex items-center gap-3">
        <div className="rounded-full border border-border px-3 py-2 text-xs text-[color:var(--text-secondary)]">Session 04 active</div>
        <button className="flex size-10 items-center justify-center rounded-full border border-border bg-panel text-[color:var(--text-secondary)]">
          <Bell className="size-4" />
        </button>
        <button className="flex size-10 items-center justify-center rounded-full border border-transparent bg-[#0f766e] text-sm text-white">T</button>
      </div>
    </div>
  );
}

function AppShellPreview() {
  return (
    <Surface className="overflow-hidden p-0">
      <div className="grid min-h-[680px] md:grid-cols-[76px_1fr]">
        <SideRail />
        <div className="grid bg-background">
          <TopBar />
          <div className="grid gap-6 p-5 md:grid-cols-[1.5fr_0.95fr] md:p-6">
            <div className="grid gap-6">
              <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border pb-4">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.18em] text-[color:var(--text-muted)]">Active session</p>
                  <h3 className="mt-2 font-serif-ui text-4xl tracking-[-0.05em] text-foreground">Website relaunch</h3>
                </div>
                <SegmentedControl />
              </div>
              <div className="grid gap-4 md:grid-cols-3">
                <SmallStat label="Questions resolved" value="48" detail="Requirement graph is stable" />
                <SmallStat label="Tasks prepared" value="19" detail="Atomic execution steps ready" />
                <SmallStat label="Blocked items" value="02" detail="Awaiting provider credentials" />
              </div>
              <div className="grid gap-4">
                <QuestionPromptBlock />
                <ChatMessageGroup />
                <ChatComposer />
              </div>
            </div>
            <div className="grid gap-4">
              <SettingsSection />
              <EmptyState />
            </div>
          </div>
        </div>
      </div>
    </Surface>
  );
}

function QuestionPromptBlock() {
  return (
    <Surface className="grid gap-4 p-6">
      <div className="flex items-center justify-between gap-3">
        <div className="grid gap-1">
          <p className="text-[11px] uppercase tracking-[0.18em] text-[color:var(--text-muted)]">Question prompt block</p>
          <h4 className="text-lg tracking-[-0.02em] text-foreground">Clarify deployment assumptions before implementation starts</h4>
        </div>
        <Button variant="ghost" size="sm">
          Review
        </Button>
      </div>
      <p className="max-w-2xl text-sm leading-7 text-[color:var(--text-secondary)]">
        The product direction is stable, but the environment model is still ambiguous. Confirm hosting, auth, storage, and external service ownership so the loop can draft execution-safe tasks.
      </p>
      <div className="grid gap-3 md:grid-cols-2">
        <ChecklistItem text="Hosting target is agreed and documented" done />
        <ChecklistItem text="External credentials ownership is assigned" done />
        <ChecklistItem text="Auth provider is still undecided" />
        <ChecklistItem text="Rate limits and cost ceilings are defined" />
      </div>
    </Surface>
  );
}

function ChecklistItem({ text, done = false }: { text: string; done?: boolean }) {
  return (
    <div className="flex items-start gap-3 rounded-[var(--radius-sm)] border border-border bg-[rgba(255,255,255,0.02)] px-4 py-3">
      <div
        className={cn(
          "mt-0.5 flex size-5 items-center justify-center rounded-full border text-[10px]",
          done
            ? "border-[rgba(155,199,154,0.5)] bg-[rgba(155,199,154,0.12)] text-[color:var(--success)]"
            : "border-border text-[color:var(--text-muted)]",
        )}
      >
        {done ? <Check className="size-3" /> : <CircleDot className="size-3" />}
      </div>
      <div className="grid gap-1">
        <p className="text-sm text-foreground">{text}</p>
        <p className="text-xs text-[color:var(--text-muted)]">{done ? "Ready for execution" : "Needs team input"}</p>
      </div>
    </div>
  );
}

function ChatMessageGroup() {
  return (
    <div className="grid gap-4">
      <div className="flex justify-end">
        <div className="max-w-[520px] rounded-[var(--radius-md)] border border-border bg-panel px-4 py-3">
          <p className="text-sm text-foreground">Build the product spec so the loop can start without contradictory assumptions.</p>
        </div>
      </div>
      <div className="flex items-start gap-3">
        <div className="mt-1 flex size-8 items-center justify-center rounded-full border border-border bg-panel text-[11px] uppercase tracking-[0.12em] text-[color:var(--text-secondary)]">
          AI
        </div>
        <div className="grid max-w-[720px] gap-3">
          <div className="rounded-[var(--radius-md)] border border-border bg-[rgba(255,255,255,0.015)] px-5 py-4">
            <p className="text-sm leading-7 text-[color:var(--text-secondary)]">
              Before I write a single line of code, I need to stabilize the execution environment. I have identified deployment, authentication, and third-party access as the remaining uncertainties.
            </p>
          </div>
          <div className="rounded-[var(--radius-md)] border border-border bg-[rgba(255,255,255,0.015)] px-5 py-4">
            <p className="text-sm leading-7 text-[color:var(--text-secondary)]">
              Once these are resolved, I can convert the requirement graph into a sequence of atomic tasks with testable success criteria.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function ChatComposer() {
  return (
    <Surface className="grid gap-4 p-4 md:p-5">
      <Textarea
        defaultValue="Ask the next consistency question. Bias toward contradictions, missing ownership, and security-critical ambiguity."
        className="min-h-[132px] resize-none border-0 bg-transparent px-0 py-0 text-base focus-visible:border-transparent focus-visible:shadow-none"
      />
      <div className="flex flex-wrap items-center justify-between gap-4 border-t border-border pt-4">
        <div className="flex items-center gap-2 text-sm text-[color:var(--text-muted)]">
          <Plus className="size-4" />
          Attach repo context
        </div>
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm">
            Save draft
          </Button>
          <Button>Continue loop</Button>
        </div>
      </div>
    </Surface>
  );
}

function MetricCard({ title, value, note }: { title: string; value: string; note: string }) {
  return (
    <Card className="gap-0">
      <CardHeader className="gap-6">
        <div className="grid gap-3">
          <div className="font-serif-ui text-5xl tracking-[-0.05em] text-foreground">{value}</div>
          <div className="grid gap-1">
            <CardTitle className="text-base">{title}</CardTitle>
            <CardDescription>{note}</CardDescription>
          </div>
        </div>
      </CardHeader>
    </Card>
  );
}

function EmptyState() {
  return (
    <Surface className="grid min-h-[248px] place-items-center p-8 text-center">
      <div className="grid max-w-[280px] gap-4">
        <div className="mx-auto flex size-12 items-center justify-center rounded-full border border-border bg-panel">
          <BriefcaseBusiness className="size-5 text-[color:var(--text-secondary)]" />
        </div>
        <div className="grid gap-2">
          <h4 className="font-serif-ui text-3xl tracking-[-0.04em] text-foreground">No blocked tasks</h4>
          <p className="text-sm leading-7 text-[color:var(--text-secondary)]">
            The execution queue is clear. Append more PRD items if the team has new scope to stabilize.
          </p>
        </div>
        <Button variant="secondary">Append requirement</Button>
      </div>
    </Surface>
  );
}

function CommandSurface() {
  return (
    <div className="mx-auto w-full max-w-[620px] rounded-[var(--radius-lg)] border border-border bg-popover p-4 shadow-[var(--shadow-overlay)]">
      <div className="flex items-center gap-3 border-b border-border px-1 pb-3 text-sm text-[color:var(--text-secondary)]">
        <Command className="size-4 text-[color:var(--text-muted)]" />
        Search commands, sessions, and notes
      </div>
      <div className="grid gap-2 pt-3">
        {[
          "Create a new execution session",
          "Open project memory",
          "Review unresolved contradictions",
          "Append a new PRD item",
        ].map((item, index) => (
          <button
            key={item}
            className={cn(
              "flex items-center justify-between rounded-[var(--radius-sm)] px-3 py-3 text-left text-sm text-[color:var(--text-secondary)] transition-colors hover:bg-accent hover:text-foreground",
              index === 0 && "bg-accent text-foreground",
            )}
          >
            <span>{item}</span>
            <ChevronRight className="size-4 text-[color:var(--text-muted)]" />
          </button>
        ))}
      </div>
    </div>
  );
}

function SettingsSection() {
  return (
    <Surface className="grid gap-5 p-6">
      <div className="grid gap-2 border-b border-border pb-4">
        <p className="text-[11px] uppercase tracking-[0.18em] text-[color:var(--text-muted)]">Settings section</p>
        <h4 className="text-xl tracking-[-0.03em] text-foreground">Session ownership</h4>
        <p className="text-sm leading-7 text-[color:var(--text-secondary)]">
          Define who owns infrastructure, keys, and execution accountability before the loop can continue.
        </p>
      </div>
      <div className="grid gap-4">
        <div className="grid gap-2">
          <Label htmlFor="owner">Project owner</Label>
          <Input id="owner" defaultValue="Tomy Leone" />
        </div>
        <div className="grid gap-2">
          <Label htmlFor="team-size">Team profile</Label>
          <Select defaultValue="agency">
            <SelectTrigger id="team-size" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent align="start">
              <SelectItem value="agency">Agency team</SelectItem>
              <SelectItem value="founder">Founder operator</SelectItem>
              <SelectItem value="product">Internal product team</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="grid gap-2">
          <Label htmlFor="policy">Execution note</Label>
          <Textarea id="policy" defaultValue="You own the code, keys, and deployment risk. The loop pauses when human identity or locked services are required." />
        </div>
      </div>
      <div className="flex justify-end gap-3 border-t border-border pt-4">
        <Button variant="ghost">Cancel</Button>
        <Button>Save policy</Button>
      </div>
    </Surface>
  );
}

function FoundationShowcase() {
  return (
    <div className="grid gap-8">
      <div className="grid gap-5 md:grid-cols-[1.2fr_0.8fr]">
        <Surface className="grid gap-5 p-6 md:p-8">
          <p className="text-[11px] uppercase tracking-[0.18em] text-[color:var(--text-muted)]">Typography</p>
          <div className="grid gap-4">
            <h1 className="font-serif-ui text-5xl tracking-[-0.05em] text-foreground md:text-7xl">Calm execution, exact structure.</h1>
            <p className="max-w-2xl text-base leading-8 text-[color:var(--text-secondary)] md:text-lg">
              Serif appears only where authority matters. The rest of the product stays technical, readable, and operational for long working sessions.
            </p>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <div className="grid gap-1">
              <span className="text-[11px] uppercase tracking-[0.16em] text-[color:var(--text-muted)]">Sans body</span>
              <p className="text-sm leading-7 text-[color:var(--text-secondary)]">
                Session blocked until credentials are provided. Clarify ownership before resuming execution.
              </p>
            </div>
            <div className="grid gap-1">
              <span className="text-[11px] uppercase tracking-[0.16em] text-[color:var(--text-muted)]">Meta label</span>
              <p className="text-sm tracking-[0.12em] uppercase text-[color:var(--text-muted)]">Structured / calm / dark-first</p>
            </div>
          </div>
        </Surface>
        <Surface className="grid gap-6 p-6 md:p-8">
          <p className="text-[11px] uppercase tracking-[0.18em] text-[color:var(--text-muted)]">Color roles</p>
          <div className="grid gap-3">
            {[
              ["Canvas", "#0A0A0A"],
              ["Panel", "#131314"],
              ["Text secondary", "#B4B1A8"],
              ["Accent", "#C7D2FE"],
            ].map(([name, value]) => (
              <div key={name} className="flex items-center justify-between border-b border-border pb-3 last:border-b-0 last:pb-0">
                <div className="flex items-center gap-3">
                  <span
                    className="block size-3 rounded-full border border-white/10"
                    style={{ backgroundColor: value }}
                  />
                  <span className="text-sm text-foreground">{name}</span>
                </div>
                <span className="text-sm text-[color:var(--text-muted)]">{value}</span>
              </div>
            ))}
          </div>
        </Surface>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard title="Questions asked" value="58" note="High-confidence requirement extraction before coding" />
        <MetricCard title="Active loops" value="03" note="Parallel projects under team supervision" />
        <MetricCard title="Paused tasks" value="01" note="Human verification still required" />
      </div>
    </div>
  );
}

function PrimitiveShowcase() {
  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-center gap-3">
        <Button>Primary action</Button>
        <Button variant="secondary">Secondary action</Button>
        <Button variant="ghost">Ghost action</Button>
        <Button variant="outline">Outline action</Button>
        <Button variant="destructive">Destructive action</Button>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <Surface className="grid gap-4 p-6">
          <div className="grid gap-2">
            <Label htmlFor="project-name">Project name</Label>
            <Input id="project-name" defaultValue="justralph.it redesign" />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="priority">Session mode</Label>
            <Select defaultValue="clarify">
              <SelectTrigger id="priority" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent align="start">
                <SelectItem value="clarify">Clarify first</SelectItem>
                <SelectItem value="append">Append tasks</SelectItem>
                <SelectItem value="observe">Observe loop</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </Surface>
        <Surface className="grid gap-2 p-6">
          <Label htmlFor="instruction">Execution note</Label>
          <Textarea
            id="instruction"
            defaultValue="Ask for contradictions, missing ownership, and hidden constraints before implementation begins."
          />
        </Surface>
      </div>
    </div>
  );
}

function NavigationShowcase() {
  return (
    <div className="grid gap-6">
      <Surface className="grid gap-5 p-5 md:p-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <SearchBar />
          <SegmentedControl />
        </div>
        <TabBar />
      </Surface>
      <CommandSurface />
    </div>
  );
}

export function DesignShowcase() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-10 px-4 py-4 md:px-6 md:py-6 lg:px-8">
        <Surface className="overflow-hidden">
          <div className="grid gap-8 px-5 py-8 md:px-8 md:py-10 lg:grid-cols-[1.2fr_0.8fr] lg:items-end lg:gap-12">
            <div className="grid gap-8">
              <div className="flex flex-wrap items-center gap-3 text-[11px] uppercase tracking-[0.18em] text-[color:var(--text-muted)]">
                <span className="rounded-full border border-border px-3 py-2">Design system showcase</span>
                <span className="rounded-full border border-border px-3 py-2">Dark-first</span>
                <span className="rounded-full border border-border px-3 py-2">Agency workflow</span>
              </div>
              <div className="grid gap-5">
                <h1 className="max-w-4xl font-serif-ui text-5xl tracking-[-0.06em] text-foreground md:text-7xl lg:text-[5.5rem] lg:leading-none">
                  A disciplined AI execution workspace for structured teams.
                </h1>
                <p className="max-w-2xl text-base leading-8 text-[color:var(--text-secondary)] md:text-lg">
                  This showcase turns the design spec into a working component baseline: calm surfaces, restrained emphasis, chat-first workflows, and operational clarity.
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <Button size="lg">Review components</Button>
                <Button size="lg" variant="secondary">
                  Open app shell
                </Button>
              </div>
            </div>
            <Surface className="grid gap-4 p-6 md:p-8">
              <div className="flex items-center justify-between">
                <p className="text-[11px] uppercase tracking-[0.18em] text-[color:var(--text-muted)]">Operating model</p>
                <Clock3 className="size-4 text-[color:var(--text-muted)]" />
              </div>
              <div className="grid gap-4">
                {[
                  ["Clarify intent", "Ask enough questions to collapse ambiguity before code exists."],
                  ["Stabilize memory", "Turn answers into a contradiction-resistant requirement graph."],
                  ["Execute precisely", "Release atomic tasks only when ownership and success criteria are clear."],
                ].map(([title, detail]) => (
                  <div key={title} className="grid gap-1 border-b border-border pb-4 last:border-b-0 last:pb-0">
                    <p className="text-sm text-foreground">{title}</p>
                    <p className="text-sm leading-7 text-[color:var(--text-secondary)]">{detail}</p>
                  </div>
                ))}
              </div>
            </Surface>
          </div>
        </Surface>

        <Section
          eyebrow="Foundations"
          title="Typography, color, and quiet hierarchy"
          description="The system stays mostly neutral, uses serif sparingly for authority, and builds hierarchy through spacing, contrast, and linework instead of decorative noise."
        >
          <FoundationShowcase />
        </Section>

        <Section
          eyebrow="Primitives"
          title="Buttons, fields, and panels"
          description="Core controls are flat, deliberate, and optimized for dark surfaces. Primary actions stay rare enough to keep decision weight."
        >
          <PrimitiveShowcase />
        </Section>

        <Section
          eyebrow="Navigation"
          title="Search, tabs, and command surfaces"
          description="Navigation is understated and spatially stable. Search is global, segmented views are quiet, and command layers stay sharp and compact."
        >
          <NavigationShowcase />
        </Section>

        <Section
          eyebrow="Execution UI"
          title="Chat-first workflows with structured requirement blocks"
          description="Messages stay readable, the composer remains grounded, and requirement review blocks help keep the loop precise before execution starts."
        >
          <div className="grid gap-4">
            <QuestionPromptBlock />
            <ChatMessageGroup />
            <ChatComposer />
          </div>
        </Section>

        <Section
          eyebrow="System views"
          title="Metrics, settings, empty states, and the product shell"
          description="The layout follows the references closely: left rail, top utility bar, large workspace, and bordered sections for quieter operational trust."
        >
          <div className="grid gap-6">
            <AppShellPreview />
          </div>
        </Section>

        <footer className="flex flex-col gap-3 border-t border-border px-1 pt-6 pb-8 text-sm text-[color:var(--text-muted)] md:flex-row md:items-center md:justify-between">
          <div className="flex flex-wrap items-center gap-3">
            <span className="inline-flex items-center gap-2">
              <Bot className="size-4" />
              justralph.it showcase baseline
            </span>
            <span className="inline-flex items-center gap-2">
              <PanelLeft className="size-4" />
              Ready for real screen implementation
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-4">
            <span className="inline-flex items-center gap-2">
              <LayoutGrid className="size-4" />
              Structured, dark, quiet
            </span>
            <span className="inline-flex items-center gap-2">
              <MessageSquareText className="size-4" />
              Chat-first by default
            </span>
          </div>
        </footer>
      </div>
    </div>
  );
}
