import { useState, useRef, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Send,
  Paperclip,
  Undo2,
  Code,
  ListTodo,
  BarChart2,
  Wrench,
  Sun,
  Moon,
  Copy,
  Check,
  LogOut,
  Download,
  Trash2,
  Volume2,
  VolumeX,
  AlertCircle,
  RotateCcw,
  GitBranch,
  Pin,
  PinOff,
  SquarePen,
} from "lucide-react";
import * as AlertDialog from "@radix-ui/react-alert-dialog";
import * as Popover from "@radix-ui/react-popover";
import type { Theme } from "@/hooks/useTheme";
import { API_URL } from "@/lib/config";
import { ConfidenceMeter } from "./ConfidenceMeter";
import { ToolsetPanel } from "./ToolsetPanel";
import { ToolSuggestion } from "./ToolSuggestion";
import { useToast } from "./Toast";
import { MarkdownMessage } from "./MarkdownMessage";
import type { ChatState, ToolName, TokenUsage } from "@/hooks/useChatbot";
import { TypingIndicator } from "./TypingIndicator";
import { SuggestionChips, SuggestionChipsSidebar } from "./SuggestionChips";
import { ExpandableDetails } from "./ExpandableDetails";
import { useRelativeTime } from "@/hooks/useRelativeTime";
import { BranchSwitcher } from "./BranchSwitcher";
import type { Branch } from "@/hooks/useBranching";
import { usePinnedMessages, msgId } from "@/hooks/usePinnedMessages";
import { ConnectionStatus } from "./ConnectionStatus";
import { InlineTaskCard } from "./InlineTaskCard";
import type { WSState } from "@/hooks/useWebSocket";

/** Renders a muted relative timestamp below a message. Renders nothing if no timestamp. */
function MessageTimestamp({ timestamp }: { timestamp: number | undefined }) {
  const label = useRelativeTime(timestamp);
  if (!label) return null;
  return (
    <span className="block text-[10px] text-zinc-500 mt-0.5 leading-none select-none">
      {label}
    </span>
  );
}

const SLOW_THRESHOLD_MS = 15_000;

type RightTab = "confidence" | "tasks" | "code" | "tools";

type ChatPanelProps = {
  state: ChatState;
  onSend: (message: string) => void;
  onRalphIt: () => void;
  /** Called when user wants to review generated tasks before starting loop. */
  onReviewTasks?: () => void;
  onClearError?: () => void;
  /** true while ralphIt() is in flight (distinct from message loading). */
  ralphItLoading?: boolean;
  /** "full" = Phase 1 fullscreen two-column; "sidebar" = Phase 2 collapsed sidebar. */
  mode?: "full" | "sidebar";
  /** Theme control for the header toggle. */
  theme?: Theme;
  onThemeToggle?: () => void;
  /** Undo the last user+assistant message pair. */
  onUndo?: () => void;
  /** Called to log out and return to WelcomePage. */
  onLogout?: () => void;
  /** Clear all messages in the current session (keeps session alive). */
  onClearChat?: () => Promise<void>;
  /** Tool callbacks */
  onRunTool?: (tool: ToolName, context?: string) => void;
  onClearToolResult?: () => void;
  /** Sound notification state/toggle. */
  soundEnabled?: boolean;
  onSoundToggle?: () => void;
  /** Retry a failed message -- called with (content, originalTimestamp). */
  onRetry?: (content: string, timestamp: number) => void;
  /** Authenticated user (passed through, not used directly in rendering). */
  user?: { login: string; name: string; avatar_url: string };
  /** Branch management props. */
  branches?: Branch[];
  activeBranchId?: string;
  /** Called with the 0-based index of the user message to branch from. */
  onBranchFrom?: (msgIndex: number) => void;
  onBranchSwitch?: (id: string) => void;
  /** Start a fresh chat session. */
  onNewChat?: () => void;
  /** WebSocket connection status for the indicator dot. */
  wsStatus?: WSState;
};

/**
 * Inline error indicator + retry button for a failed user message.
 * Shown below the message text when msg.status === "error".
 */
function MessageErrorRow({
  content,
  timestamp,
  onRetry,
  compact = false,
}: {
  content: string;
  timestamp: number | undefined;
  onRetry?: (content: string, timestamp: number) => void;
  compact?: boolean;
}) {
  if (!onRetry || timestamp === undefined) return null;
  const iconClass = compact ? "size-3" : "size-3.5";
  const textClass = compact ? "text-[10px]" : "text-xs";
  return (
    <span className={["flex items-center gap-1 mt-0.5", textClass].join(" ")}>
      <AlertCircle className={[iconClass, "text-destructive shrink-0"].join(" ")} />
      <span className="text-destructive uppercase tracking-wider">SEND FAILED</span>
      <button
        onClick={() => onRetry(content, timestamp)}
        title="Retry sending this message"
        className="flex items-center gap-0.5 text-destructive hover:text-destructive/80 border border-destructive/50 hover:border-destructive px-1 py-0.5 transition-colors ml-0.5"
      >
        <RotateCcw className={iconClass} />
        <span className="uppercase tracking-wider">RETRY</span>
      </button>
    </span>
  );
}

/**
 * Shows estimated/actual token count below an assistant message.
 * Click to expand into input/output breakdown when both values are available.
 */
function TokenBadge({ usage }: { usage: TokenUsage }) {
  const [expanded, setExpanded] = useState(false);
  const hasBreakdown = usage.inputTokens !== undefined;

  const label = `~${usage.outputTokens.toLocaleString()} tokens${usage.estimated ? "" : ""}`;

  if (!hasBreakdown) {
    return (
      <span className="text-xs text-zinc-500 select-none">
        {label}
      </span>
    );
  }

  return (
    <button
      onClick={() => setExpanded((v) => !v)}
      title={expanded ? "Hide breakdown" : "Show input/output breakdown"}
      className="text-xs text-zinc-500 hover:text-zinc-400 transition-colors text-left"
    >
      {expanded ? (
        <span>
          in: {usage.inputTokens!.toLocaleString()} / out: {usage.outputTokens.toLocaleString()} tokens
        </span>
      ) : (
        label
      )}
    </button>
  );
}

/** Copy button: shows Copy icon, switches to Check for 2s after click. */
function CopyButton({ text, size = "default" }: { text: string; size?: "default" | "sm" }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard unavailable -- silently ignore
    }
  };

  const iconClass = size === "sm" ? "size-3" : "size-3.5";
  return (
    <button
      onClick={handleCopy}
      title="Copy message"
      className="shrink-0 text-muted-foreground hover:text-primary opacity-0 group-hover:opacity-100 transition-opacity"
    >
      {copied ? <Check className={iconClass} /> : <Copy className={iconClass} />}
    </button>
  );
}

/** Branch button: shown on user messages on hover, forks the conversation from that point. */
function BranchButton({
  onClick,
  size = "default",
}: {
  onClick: () => void;
  size?: "default" | "sm";
}) {
  const iconClass = size === "sm" ? "size-3" : "size-3.5";
  return (
    <button
      onClick={onClick}
      title="Branch from here"
      className="shrink-0 text-muted-foreground hover:text-primary opacity-0 group-hover:opacity-100 transition-opacity"
    >
      <GitBranch className={iconClass} />
    </button>
  );
}

/** Pin button: toggles pin state. Always visible when pinned; shows on hover otherwise. */
function PinButton({
  pinned,
  onToggle,
  size = "default",
}: {
  pinned: boolean;
  onToggle: () => void;
  size?: "default" | "sm";
}) {
  const iconClass = size === "sm" ? "size-3" : "size-3.5";
  return (
    <button
      onClick={onToggle}
      title={pinned ? "Unpin message" : "Pin message"}
      className={[
        "shrink-0 transition-opacity",
        pinned
          ? "text-primary opacity-100"
          : "text-muted-foreground hover:text-primary opacity-0 group-hover:opacity-100",
      ].join(" ")}
    >
      {pinned ? <PinOff className={iconClass} /> : <Pin className={iconClass} />}
    </button>
  );
}

/**
 * Header button that opens a popover listing pinned messages.
 * Clicking an entry closes the popover and scrolls to the message.
 */
function PinsDropdown({
  pinnedMessages,
  onScrollTo,
  size = "default",
}: {
  pinnedMessages: { id: string; label: string }[];
  onScrollTo: (id: string) => void;
  size?: "default" | "sm";
}) {
  const count = pinnedMessages.length;
  const btnClass =
    size === "sm"
      ? "flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-muted-foreground hover:text-primary transition-colors disabled:opacity-30"
      : "flex items-center gap-1 text-xs font-bold uppercase tracking-wider text-muted-foreground hover:text-primary transition-colors disabled:opacity-30";
  const iconClass = size === "sm" ? "size-3" : "size-3.5";

  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        <button
          className={btnClass}
          disabled={count === 0}
          title={count === 0 ? "No pinned messages" : `${count} pinned`}
        >
          <Pin className={iconClass} />
          {size !== "sm" && <span>PINS{count > 0 ? ` (${count})` : ""}</span>}
          {size === "sm" && count > 0 && <span>{count}</span>}
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          side="bottom"
          align="end"
          sideOffset={6}
          className="z-50 w-72 bg-card border border-border shadow-xl font-mono"
        >
          <div className="px-3 py-2 border-b border-border">
            <p className="text-xs font-bold uppercase tracking-wider text-foreground">
              PINNED MESSAGES
            </p>
          </div>
          <ul className="max-h-64 overflow-y-auto divide-y divide-border">
            {pinnedMessages.map(({ id, label }) => (
              <li key={id}>
                <Popover.Close asChild>
                  <button
                    onClick={() => onScrollTo(id)}
                    className="w-full text-left px-3 py-2 text-xs text-muted-foreground hover:text-primary hover:bg-muted/30 transition-colors truncate"
                    title={label}
                  >
                    <Pin className="inline size-2.5 mr-1.5 text-primary" />
                    {label}
                  </button>
                </Popover.Close>
              </li>
            ))}
          </ul>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

/** Shared file upload handler used in both modes. */
function FileInput({
  sessionId,
  onSend,
  size = "default",
}: {
  sessionId: string | null;
  onSend: (msg: string) => void;
  size?: "default" | "sm";
}) {
  const fileRef = useRef<HTMLInputElement>(null);
  const sizeClass = size === "sm" ? "size-7 shrink-0" : "size-8 shrink-0";
  const iconClass = size === "sm" ? "size-3" : "size-4";

  return (
    <>
      <button
        className={[
          sizeClass,
          "border border-border text-muted-foreground hover:text-primary hover:border-primary transition-colors flex items-center justify-center bg-transparent",
          !sessionId ? "opacity-40 cursor-not-allowed" : "",
        ].join(" ")}
        onClick={() => fileRef.current?.click()}
        title="Attach files"
        disabled={!sessionId}
      >
        <Paperclip className={iconClass} />
      </button>
      <input
        ref={fileRef}
        type="file"
        multiple
        className="hidden"
        onChange={async (e) => {
          if (!sessionId || !e.target.files) return;
          for (const file of Array.from(e.target.files)) {
            const form = new FormData();
            form.append("file", file);
            await fetch(`${API_URL}/api/sessions/${sessionId}/uploads`, {
              method: "POST",
              body: form,
            });
          }
          onSend(`[Attached ${e.target.files.length} file(s)]`);
          e.target.value = "";
        }}
      />
    </>
  );
}

/** Right-side tabbed panel shown in full mode. */
function RightTabPanel({
  state,
  onRalphIt,
  onReviewTasks,
  ralphItLoading,
  slowLoad,
  busy,
  onRunTool,
}: {
  state: ChatState;
  onRalphIt: () => void;
  onReviewTasks?: () => void;
  ralphItLoading: boolean;
  slowLoad: boolean;
  busy: boolean;
  onRunTool?: (tool: ToolName, context?: string) => void;
}) {
  const [activeTab, setActiveTab] = useState<RightTab>("confidence");

  const tabs: { id: RightTab; label: string; icon: React.ReactNode }[] = [
    { id: "confidence", label: "CONFIDENCE", icon: <BarChart2 className="size-3" /> },
    { id: "tasks", label: "TASKS", icon: <ListTodo className="size-3" /> },
    { id: "code", label: "CODE", icon: <Code className="size-3" /> },
    { id: "tools", label: "TOOLS", icon: <Wrench className="size-3" /> },
  ];

  return (
    <div className="flex flex-col h-full bg-card border-l border-border">
      {/* Tab bar */}
      <div className="flex border-b border-border shrink-0">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={[
              "flex-1 flex items-center justify-center gap-1.5 py-2.5 text-xs font-bold uppercase tracking-wider transition-colors",
              activeTab === tab.id
                ? "text-primary border-b-2 border-primary"
                : "text-muted-foreground hover:text-primary",
            ].join(" ")}
          >
            {tab.icon}
            {tab.label}
            {tab.id === "tools" && state.toolResult && (
              <span className="size-1.5 rounded-full bg-[#FFaa00] ml-1" />
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto p-4">
        {activeTab === "confidence" && (
          <ConfidenceMeter
            confidence={state.confidence}
            relevance={state.relevance}
            weightedReadiness={state.weightedReadiness}
            questionCount={state.questionCount}
            phase={state.phase}
            ready={state.ready}
          />
        )}
        {activeTab === "tasks" && (
          <div className="space-y-2">
            {state.tasks && state.tasks.length > 0 ? (
              state.tasks.map((task: any, i: number) => (
                <div
                  key={i}
                  className="border border-border px-3 py-2 bg-background"
                >
                  <p className="text-xs font-bold text-foreground uppercase truncate">
                    {task.title ?? task.name ?? `TASK ${i + 1}`}
                  </p>
                  {task.body && (
                    <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                      {task.body}
                    </p>
                  )}
                </div>
              ))
            ) : (
              <p className="text-xs text-muted-foreground uppercase tracking-wider text-center py-8">
                TASKS WILL APPEAR WHEN RALPH IS READY.
              </p>
            )}
          </div>
        )}
        {activeTab === "code" && (
          <p className="text-xs text-muted-foreground uppercase tracking-wider text-center py-8">
            CODE CHANGES WILL APPEAR WHEN THE LOOP STARTS.
          </p>
        )}
        {activeTab === "tools" && onRunTool && (
          <ToolsetPanel
            state={state}
            onRunTool={onRunTool}
            toolLoading={state.toolLoading}
            activeTool={state.toolLoadingId ?? null}
          />
        )}
        {activeTab === "tools" && !onRunTool && (
          <p className="text-xs text-muted-foreground uppercase tracking-wider text-center py-8">
            TOOLS NOT AVAILABLE.
          </p>
        )}
      </div>

      {/* Action button */}
      {state.ready && (
        <div className="p-4 border-t border-border shrink-0 space-y-2">
          {onReviewTasks ? (
            <button
              onClick={onReviewTasks}
              disabled={busy}
              className="w-full border-2 border-primary bg-transparent text-primary hover:bg-primary hover:text-primary-foreground uppercase tracking-wider text-sm font-bold py-3 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              REVIEW TASKS
            </button>
          ) : (
            <button
              onClick={onRalphIt}
              disabled={busy}
              className="w-full border-2 border-primary bg-transparent text-primary hover:bg-primary hover:text-primary-foreground uppercase tracking-wider text-sm font-bold py-3 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {ralphItLoading ? "CREATING PROJECT..." : "JUST RALPH IT"}
            </button>
          )}
          {slowLoad && !onReviewTasks && (
            <p className="text-xs text-muted-foreground uppercase tracking-wider text-center">
              THIS IS TAKING A WHILE...
            </p>
          )}
        </div>
      )}
    </div>
  );
}

/** Trash icon button with Radix AlertDialog confirmation before clearing. */
function ClearChatButton({
  onConfirm,
  size = "default",
  disabled = false,
}: {
  onConfirm: () => Promise<void>;
  size?: "default" | "sm";
  disabled?: boolean;
}) {
  const iconClass = size === "sm" ? "size-3" : "size-3.5";
  const btnClass =
    size === "sm"
      ? "shrink-0 text-muted-foreground hover:text-destructive opacity-60 hover:opacity-100 transition-colors disabled:pointer-events-none disabled:opacity-30"
      : "shrink-0 text-muted-foreground hover:text-destructive transition-colors disabled:pointer-events-none disabled:opacity-30";

  return (
    <AlertDialog.Root>
      <AlertDialog.Trigger asChild>
        <button className={btnClass} title="Clear chat" disabled={disabled}>
          <Trash2 className={iconClass} />
        </button>
      </AlertDialog.Trigger>

      <AlertDialog.Portal>
        <AlertDialog.Overlay className="fixed inset-0 bg-black/60 z-50" />
        <AlertDialog.Content className="fixed left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2 w-full max-w-sm bg-card border border-border p-6 font-mono shadow-xl">
          <AlertDialog.Title className="text-sm font-bold uppercase tracking-wider text-foreground mb-2">
            CLEAR CHAT?
          </AlertDialog.Title>
          <AlertDialog.Description className="text-xs text-muted-foreground uppercase tracking-wider mb-6">
            ALL MESSAGES WILL BE DELETED AND CONFIDENCE SCORES RESET. THE SESSION WILL REMAIN ACTIVE.
          </AlertDialog.Description>
          <div className="flex gap-3 justify-end">
            <AlertDialog.Cancel asChild>
              <button className="border border-border text-muted-foreground hover:text-foreground hover:border-foreground uppercase tracking-wider text-xs font-bold px-4 py-2 transition-colors">
                CANCEL
              </button>
            </AlertDialog.Cancel>
            <AlertDialog.Action asChild>
              <button
                onClick={onConfirm}
                className="border border-destructive bg-transparent text-destructive hover:bg-destructive hover:text-destructive-foreground uppercase tracking-wider text-xs font-bold px-4 py-2 transition-colors"
              >
                CLEAR
              </button>
            </AlertDialog.Action>
          </div>
        </AlertDialog.Content>
      </AlertDialog.Portal>
    </AlertDialog.Root>
  );
}

export function ChatPanel({
  state,
  onSend,
  onRalphIt,
  onReviewTasks,
  onClearError,
  ralphItLoading = false,
  mode = "full",
  onUndo,
  theme,
  onThemeToggle,
  onLogout,
  onClearChat,
  onRunTool,
  onClearToolResult,
  soundEnabled,
  onSoundToggle,
  onRetry,
  branches = [],
  activeBranchId = "main",
  onBranchFrom,
  onBranchSwitch,
  user,
  onNewChat,
  wsStatus,
}: ChatPanelProps) {
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const sidebarTextareaRef = useRef<HTMLTextAreaElement>(null);
  const { toast } = useToast();

  // Pinned messages -- keyed by sessionId in localStorage
  const { isPinned, togglePin } = usePinnedMessages(state.sessionId);

  /** Scroll the message with the given DOM id into view. */
  const scrollToMessage = useCallback((id: string) => {
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
  }, []);

  /** Grow textarea to scrollHeight, capped by max-height CSS. */
  const autoResize = (el: HTMLTextAreaElement | null) => {
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  };

  /** Reset textarea to single-line height after send. */
  const resetHeight = (el: HTMLTextAreaElement | null) => {
    if (!el) return;
    el.style.height = "auto";
  };

  // Timeout indicator: shown if ralphItLoading has been true >15s
  const [slowLoad, setSlowLoad] = useState(false);
  useEffect(() => {
    if (!ralphItLoading) {
      setSlowLoad(false);
      return;
    }
    const t = setTimeout(() => setSlowLoad(true), SLOW_THRESHOLD_MS);
    return () => clearTimeout(t);
  }, [ralphItLoading]);

  // Elapsed seconds counter while loading
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  useEffect(() => {
    if (!state.loading) {
      setElapsedSeconds(0);
      return;
    }
    setElapsedSeconds(0);
    const interval = setInterval(() => setElapsedSeconds((s) => s + 1), 1000);
    return () => clearInterval(interval);
  }, [state.loading]);

  // Consume transient errors from hook state -> toast
  useEffect(() => {
    if (!state.error) return;
    toast("Failed to send message", "error");
    onClearError?.();
  }, [state.error, toast, onClearError]);

  useEffect(() => {
    scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight);
  }, [state.messages.length]);

  // Auto-scroll when a tool suggestion banner appears (it pushes content up)
  useEffect(() => {
    if (state.toolResult) {
      scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight);
    }
  }, [state.toolResult]);

  // Global Ctrl+K / Cmd+K -> new chat
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        onNewChat?.();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onNewChat]);

  // Drag-and-drop state
  const [isDragging, setIsDragging] = useState(false);
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const dragCounterRef = useRef(0);

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    dragCounterRef.current += 1;
    if (dragCounterRef.current === 1) setIsDragging(true);
  };
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };
  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    dragCounterRef.current -= 1;
    if (dragCounterRef.current === 0) setIsDragging(false);
  };
  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    dragCounterRef.current = 0;
    setIsDragging(false);
    const files = Array.from(e.dataTransfer.files);
    if (!files.length) return;
    if (!state.sessionId) {
      setPendingFiles((prev) => [...prev, ...files]);
      return;
    }
    const uploaded: File[] = [];
    for (const file of files) {
      const form = new FormData();
      form.append("file", file);
      try {
        await fetch(`${API_URL}/api/sessions/${state.sessionId}/uploads`, {
          method: "POST",
          body: form,
        });
        uploaded.push(file);
      } catch {
        // best-effort
      }
    }
    if (uploaded.length > 0) {
      onSend(`[Attached ${uploaded.length} file(s): ${uploaded.map((f) => f.name).join(", ")}]`);
    }
  };
  const removePendingFile = (idx: number) => {
    setPendingFiles((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleSend = () => {
    const msg = input.trim();
    if (!msg || state.loading) return;
    setInput("");
    resetHeight(textareaRef.current);
    resetHeight(sidebarTextareaRef.current);
    setPendingFiles([]);
    onSend(msg);
  };

  const busy = state.loading || ralphItLoading;

  /** Build ordered list of pinned messages for PinsDropdown, preserving message order. */
  const pinnedList = state.messages
    .map((msg, i) => {
      const id = msgId(msg.role, msg.content);
      if (!isPinned(id)) return null;
      const label =
        msg.content.length > 60 ? msg.content.slice(0, 60) + "..." : msg.content;
      return { id: `msg-${i}`, label };
    })
    .filter((x): x is { id: string; label: string } => x !== null);

  // ----------------------------- sidebar mode -----------------------------
  if (mode === "sidebar") {
    return (
      <div className="h-full flex flex-col bg-card border-r border-border overflow-hidden">
        {/* Compact header */}
        <div className="px-3 py-3 border-b border-border shrink-0 flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <h2 className="text-xs font-bold text-muted-foreground uppercase tracking-wider">
              CHAT
            </h2>
            {wsStatus && <ConnectionStatus status={wsStatus} />}
          </div>
          <div className="flex items-center gap-2">
            {onNewChat && (
              <button
                onClick={onNewChat}
                title="New chat (Ctrl+K)"
                className="shrink-0 text-muted-foreground hover:text-primary transition-colors"
              >
                <SquarePen className="size-3" />
              </button>
            )}
            <PinsDropdown
              pinnedMessages={pinnedList}
              onScrollTo={scrollToMessage}
              size="sm"
            />
            {onClearChat && (
              <ClearChatButton
                onConfirm={onClearChat}
                size="sm"
                disabled={busy || state.messages.length === 0}
              />
            )}
          </div>
        </div>

        {/* Branch switcher (only shown when branches exist) */}
        {onBranchSwitch && (
          <BranchSwitcher
            branches={branches}
            activeBranchId={activeBranchId}
            onSwitch={onBranchSwitch}
            size="sm"
          />
        )}

        {/* Messages */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-2 py-1">
          {state.messages.length === 0 && (
            <div className="flex flex-col justify-center h-full text-muted-foreground text-xs text-center py-6 px-2 uppercase tracking-wider">
              <p>NO MESSAGES YET.</p>
            </div>
          )}
          {state.messages.map((msg, i) => {
            const lastUserIdx =
              state.messages.length >= 2
                ? state.messages.map((m) => m.role).lastIndexOf("user")
                : -1;
            const showUndo =
              onUndo && msg.role === "user" && i === lastUserIdx && state.messages.length >= 2;
            const canBranch = onBranchFrom && msg.role === "user";
            const isError = msg.status === "error";
            const id = msgId(msg.role, msg.content);
            const pinned = isPinned(id);
            return (
              <div
                key={i}
                id={`msg-${i}`}
                className={[
                  "group border-b py-2 flex items-start gap-1",
                  isError ? "border-destructive/40 bg-destructive/5" : "border-border",
                  pinned ? "border-l-2 border-l-primary pl-1" : "",
                ].join(" ")}
              >
                {showUndo && (
                  <button
                    className="shrink-0 text-muted-foreground hover:text-primary opacity-60 hover:opacity-100 mt-0.5"
                    title="Undo last message"
                    onClick={onUndo}
                  >
                    <Undo2 className="size-3" />
                  </button>
                )}
                <div className="flex-1 min-w-0">
                  {msg.role === "user" ? (
                    <p className={["text-xs whitespace-pre-wrap break-words", isError ? "text-destructive/80" : "text-primary"].join(" ")}>
                      <span className={isError ? "text-destructive/80" : "text-primary"}>&gt; </span>
                      {msg.content}
                    </p>
                  ) : (
                    <div>
                      <span className="text-xs font-mono text-foreground">$ </span>
                      <MarkdownMessage content={msg.content} className="text-xs" />
                    </div>
                  )}
                  {isError && (
                    <MessageErrorRow
                      content={msg.content}
                      timestamp={msg.timestamp}
                      onRetry={onRetry}
                      compact
                    />
                  )}
                  <MessageTimestamp timestamp={msg.timestamp} />
                  {msg.role === "assistant" && msg.tokenUsage && (
                    <span className="block mt-0.5 font-mono">
                      <TokenBadge usage={msg.tokenUsage} />
                    </span>
                  )}
                  {msg.role === "assistant" && msg.metadata && (
                    <ExpandableDetails metadata={msg.metadata} compact />
                  )}
                </div>
                {canBranch && (
                  <BranchButton onClick={() => onBranchFrom(i)} size="sm" />
                )}
                <PinButton pinned={pinned} onToggle={() => togglePin(id)} size="sm" />
                <CopyButton text={msg.content} size="sm" />
              </div>
            );
          })}
          {state.loading && (
            <TypingIndicator elapsedSeconds={elapsedSeconds} compact />
          )}
        </div>

        {/* Ready actions (sidebar) */}
        {state.ready && (
          <div className="px-2 pb-2 shrink-0">
            {onReviewTasks ? (
              <button
                onClick={onReviewTasks}
                disabled={busy}
                className="w-full border border-primary bg-transparent text-primary hover:bg-primary hover:text-primary-foreground uppercase tracking-wider text-xs font-bold py-1.5 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                REVIEW TASKS
              </button>
            ) : (
              <button
                onClick={onRalphIt}
                disabled={busy}
                className="w-full border border-primary bg-transparent text-primary hover:bg-primary hover:text-primary-foreground uppercase tracking-wider text-xs font-bold py-1.5 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {ralphItLoading ? "CREATING..." : "RALPH IT"}
              </button>
            )}
          </div>
        )}

        {/* Tool suggestion banner (sidebar) */}
        {state.toolResult && onClearToolResult && (
          <ToolSuggestion
            result={state.toolResult}
            onUse={(text) => { setInput(text); onClearToolResult(); }}
            onEdit={(text) => { setInput(text); onClearToolResult(); }}
            onDismiss={onClearToolResult}
          />
        )}

        {/* Input */}
        <div className="border-t border-border p-2 shrink-0">
          <div className="flex gap-1 items-end">
            <FileInput sessionId={state.sessionId} onSend={onSend} size="sm" />
            <textarea
              ref={sidebarTextareaRef}
              value={input}
              rows={1}
              onChange={(e) => {
                setInput(e.target.value);
                autoResize(e.target);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }
                else if (e.key === "Escape") setInput("");
              }}
              placeholder="MSG..."
              disabled={busy}
              className="flex-1 text-xs bg-transparent border border-border text-primary placeholder:text-muted-foreground px-2 py-1 outline-none focus:border-primary transition-colors resize-none overflow-y-auto max-h-[200px] leading-5"
            />
            <button
              onClick={handleSend}
              disabled={busy || !input.trim()}
              className="size-7 shrink-0 border border-primary bg-transparent text-primary hover:bg-primary hover:text-primary-foreground transition-colors flex items-center justify-center disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Send className="size-3" />
            </button>
          </div>
          {input.length > 0 && (
            <p className="text-xs text-zinc-500 mt-1 text-right">
              {input.length} chars / {input.trim().split(/\s+/).length} words
            </p>
          )}
        </div>
      </div>
    );
  }

  // ----------------------------- full mode (two columns) -----------------
  return (
    <div className="h-screen flex bg-background overflow-hidden">
      {/* LEFT column: header + messages + input */}
      <div className="flex-1 flex flex-col min-w-0 border-r border-border">
        {/* Header */}
        <div className="border-b border-border px-6 py-4 shrink-0 flex items-start justify-between">
          <div>
            <h1 className="text-xl font-bold uppercase tracking-[0.15em] text-foreground">
              JUSTRALPH.IT
            </h1>
            <p className="text-primary text-xs uppercase tracking-widest mt-1">
              DESCRIBE YOUR PROJECT. RALPH BUILDS IT.
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {wsStatus && <ConnectionStatus status={wsStatus} />}
            {onNewChat && (
              <button
                onClick={onNewChat}
                title="New chat (Ctrl+K)"
                className="text-muted-foreground hover:text-primary transition-colors"
              >
                <SquarePen className="size-4" />
              </button>
            )}
            <PinsDropdown
              pinnedMessages={pinnedList}
              onScrollTo={scrollToMessage}
            />
            {onSoundToggle && (
              <button
                onClick={onSoundToggle}
                aria-label={soundEnabled ? "Disable sound notifications" : "Enable sound notifications"}
                title={soundEnabled ? "Sound: ON" : "Sound: OFF"}
                className="text-primary hover:opacity-70 transition-opacity"
              >
                {soundEnabled ? <Volume2 className="size-4" /> : <VolumeX className="size-4" />}
              </button>
            )}
            {onThemeToggle && (
              <button
                onClick={onThemeToggle}
                aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
                title={theme === "dark" ? "Light mode" : "Dark mode"}
                className="text-primary hover:opacity-70 transition-opacity"
              >
                {theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
              </button>
            )}
            {onClearChat && (
              <ClearChatButton
                onConfirm={onClearChat}
                disabled={busy || state.messages.length === 0}
              />
            )}
            {onLogout && (
              <button
                onClick={onLogout}
                title="Log out"
                aria-label="Log out"
                className="p-1 border border-border hover:border-destructive text-muted-foreground hover:text-destructive transition-colors"
              >
                <LogOut className="size-4" />
              </button>
            )}
          </div>
        </div>

        {/* Branch switcher (only shown when branches exist) */}
        {onBranchSwitch && (
          <BranchSwitcher
            branches={branches}
            activeBranchId={activeBranchId}
            onSwitch={onBranchSwitch}
          />
        )}

        {/* Messages with drag-and-drop overlay */}
        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto px-6 py-2 relative"
          onDragEnter={handleDragEnter}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          {isDragging && (
            <div className="absolute inset-0 z-10 flex items-center justify-center border-2 border-dashed border-primary bg-background/80 pointer-events-none">
              <p className="text-primary font-mono text-sm uppercase tracking-wider">
                DROP FILES HERE
              </p>
            </div>
          )}
          {state.messages.length === 0 && (
            <div className="flex flex-col justify-center h-full text-muted-foreground uppercase tracking-wider text-center">
              <p className="text-sm font-bold">WHAT DO YOU WANT TO BUILD?</p>
              <p className="text-xs mt-1">DESCRIBE YOUR IDEA AND RALPH WILL TAKE IT FROM THERE.</p>
            </div>
          )}
          {state.messages.map((msg, i) => {
            const lastUserIdx =
              state.messages.length >= 2
                ? state.messages.map((m) => m.role).lastIndexOf("user")
                : -1;
            const showUndo =
              onUndo && msg.role === "user" && i === lastUserIdx && state.messages.length >= 2;
            const canBranch = onBranchFrom && msg.role === "user";
            const isError = msg.status === "error";
            const id = msgId(msg.role, msg.content);
            const pinned = isPinned(id);
            return (
              <div
                key={i}
                id={`msg-${i}`}
                className={[
                  "group border-b py-3 flex items-start gap-2",
                  isError ? "border-destructive/40 bg-destructive/5" : "border-border",
                  pinned ? "border-l-2 border-l-primary pl-2" : "",
                ].join(" ")}
              >
                {showUndo && (
                  <button
                    className="shrink-0 text-muted-foreground hover:text-primary opacity-60 hover:opacity-100 mt-0.5"
                    title="Undo last message"
                    onClick={onUndo}
                  >
                    <Undo2 className="size-3.5" />
                  </button>
                )}
                <div className="flex-1 min-w-0">
                  {msg.role === "user" ? (
                    <p className={["text-sm whitespace-pre-wrap break-words", isError ? "text-destructive/80" : "text-primary"].join(" ")}>
                      <span className={["font-bold mr-1", isError ? "text-destructive/80" : ""].join(" ")}>&gt; </span>
                      {msg.content}
                    </p>
                  ) : (
                    <div>
                      <span className="text-sm font-bold mr-1 font-mono text-foreground">$ </span>
                      <MarkdownMessage content={msg.content} />
                    </div>
                  )}
                  {isError && (
                    <MessageErrorRow
                      content={msg.content}
                      timestamp={msg.timestamp}
                      onRetry={onRetry}
                    />
                  )}
                  <MessageTimestamp timestamp={msg.timestamp} />
                  {msg.role === "assistant" && msg.tokenUsage && (
                    <span className="block mt-0.5 font-mono">
                      <TokenBadge usage={msg.tokenUsage} />
                    </span>
                  )}
                  {msg.role === "assistant" && msg.metadata && (
                    <ExpandableDetails metadata={msg.metadata} />
                  )}
                </div>
                {canBranch && (
                  <BranchButton onClick={() => onBranchFrom(i)} />
                )}
                <PinButton pinned={pinned} onToggle={() => togglePin(id)} />
                <CopyButton text={msg.content} />
              </div>
            );
          })}
          {state.loading && (
            <TypingIndicator elapsedSeconds={elapsedSeconds} />
          )}
          {/* Inline task cards -- rendered after last assistant message when ready */}
          {state.ready && state.tasks && state.tasks.length > 0 && state.sessionId && (
            <div className="mt-3 space-y-1 pb-2">
              <p className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1">
                TASKS (click to edit)
              </p>
              {state.tasks.map((task: any) => (
                <InlineTaskCard
                  key={task.id ?? task.title}
                  task={{ id: task.id ?? task.title, title: task.title ?? task.name ?? "", priority: task.priority, status: task.status }}
                  sessionId={state.sessionId!}
                />
              ))}
            </div>
          )}
        </div>

        {/* Tool suggestion banner */}
        {state.toolResult && onClearToolResult && (
          <ToolSuggestion
            result={state.toolResult}
            onUse={(text) => { setInput(text); onClearToolResult(); }}
            onEdit={(text) => { setInput(text); onClearToolResult(); }}
            onDismiss={onClearToolResult}
          />
        )}

        {/* Pending file chips (from drag-and-drop before session exists) */}
        {pendingFiles.length > 0 && (
          <div className="px-4 pt-2 flex flex-wrap gap-1 shrink-0">
            {pendingFiles.map((f, idx) => (
              <span
                key={idx}
                className="flex items-center gap-1 text-[10px] font-mono border border-border bg-card px-2 py-0.5 text-muted-foreground"
              >
                {f.name}
                <button
                  onClick={() => removePendingFile(idx)}
                  className="hover:text-destructive ml-0.5"
                  title="Remove"
                >
                  &times;
                </button>
              </span>
            ))}
          </div>
        )}

        {/* Input bar */}
        <div className="border-t border-border p-4 shrink-0">
          <div className="flex gap-2 items-end">
            <FileInput sessionId={state.sessionId} onSend={onSend} />
            <span className="text-primary font-bold text-sm shrink-0 pb-2">&gt;</span>
            <textarea
              ref={textareaRef}
              value={input}
              rows={1}
              onChange={(e) => {
                setInput(e.target.value);
                autoResize(e.target);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }
                else if (e.key === "Escape") setInput("");
              }}
              placeholder="DESCRIBE YOUR PROJECT..."
              disabled={busy}
              className="flex-1 bg-transparent border border-border text-primary placeholder:text-muted-foreground px-3 py-2 text-sm outline-none focus:border-primary transition-colors resize-none overflow-y-auto max-h-[200px] leading-5"
            />
            <button
              onClick={handleSend}
              disabled={busy || !input.trim()}
              className="border border-primary bg-transparent text-primary hover:bg-primary hover:text-primary-foreground transition-colors px-3 py-2 flex items-center justify-center disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Send className="size-4" />
            </button>
          </div>
          {input.length > 0 && (
            <p className="text-xs text-zinc-500 mt-2 text-right">
              {input.length} chars / {input.trim().split(/\s+/).length} words
            </p>
          )}
        </div>
      </div>

      {/* RIGHT column: tabbed panel (w-80) */}
      <div className="w-80 shrink-0 flex flex-col overflow-hidden">
        <RightTabPanel
          state={state}
          onRalphIt={onRalphIt}
          onReviewTasks={onReviewTasks}
          ralphItLoading={ralphItLoading}
          slowLoad={slowLoad}
          busy={busy}
          onRunTool={onRunTool}
        />
      </div>
    </div>
  );
}
