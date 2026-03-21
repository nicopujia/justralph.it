import { Paperclip, Plus, SendHorizontal, X } from "lucide-react";
import type { ChangeEvent } from "react";
import { useEffect, useRef, useState } from "react";

import { type ChatEntry } from "@/components/system/app-data";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

type ProjectChatPanelProps = {
  projectName: string;
  entries: ChatEntry[];
};

export function ProjectChatPanel({ projectName, entries }: ProjectChatPanelProps) {
  const [messages, setMessages] = useState<ChatEntry[]>(entries);
  const [draft, setDraft] = useState("");
  const [attachments, setAttachments] = useState<string[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setMessages(entries);
    setDraft("");
    setAttachments([]);
  }, [entries, projectName]);

  function handleAttachClick() {
    fileInputRef.current?.click();
  }

  function handleAttachFile(event: ChangeEvent<HTMLInputElement>) {
    const selectedFiles = Array.from(event.target.files ?? []).map(file => file.name);

    if (selectedFiles.length === 0) {
      return;
    }

    setAttachments(current => {
      const next = new Set(current);
      selectedFiles.forEach(name => next.add(name));
      return Array.from(next);
    });

    event.target.value = "";
  }

  function handleRemoveAttachment(name: string) {
    setAttachments(current => current.filter(item => item !== name));
  }

  function handleContinue() {
    if (!draft.trim() && attachments.length === 0) {
      return;
    }

    const nextMessages: ChatEntry[] = [...messages];

    if (draft.trim()) {
      nextMessages.push({ id: `user-${Date.now()}`, role: "user", text: draft.trim() });
    }

    if (attachments.length > 0) {
      nextMessages.push({
        id: `assistant-${Date.now()}`,
        role: "assistant",
        text: `I registered ${attachments.join(", ")} as context for this project. I will keep the plan constrained to the attached material and continue from the unresolved requirements only.`,
        cta: "just ralph it",
      });
    } else {
      nextMessages.push({
        id: `assistant-${Date.now()}`,
        role: "assistant",
        text: "I updated the plan with the new instruction and reduced the next pass to the unresolved decisions only. The remaining blockers are still ownership, launch timing, and notification routing.",
        cta: "just ralph it",
      });
    }

    setMessages(nextMessages);
    setDraft("");
    setAttachments([]);
  }

  return (
    <section className="ml-3 flex h-full min-h-0 flex-col border-r border-border bg-[#0f0f10]">
      <div className="border-b border-border px-5 py-4">
        <p className="text-[11px] uppercase tracking-[0.18em] text-[color:var(--text-muted)]">Project</p>
        <h2 className="mt-2 text-lg tracking-[-0.03em] text-foreground">{projectName}</h2>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5">
        <div className="grid gap-5">
          {messages.map(entry => (
            <article key={entry.id} className={cn("grid gap-3", entry.role === "user" ? "justify-items-end" : "justify-items-start")}>
              {entry.role === "assistant" ? (
                <div className="max-w-[95%] text-sm leading-7 text-[#e3e1db]">{entry.text}</div>
              ) : (
                <div className="max-w-[90%] rounded-[var(--radius-md)] border border-[rgba(255,255,255,0.14)] bg-[#19191b] px-4 py-3 text-sm leading-7 text-foreground">
                  {entry.text}
                </div>
              )}

              {entry.role === "assistant" && entry.cta ? (
                <Button variant="secondary" size="sm" className="h-9 bg-[rgba(255,255,255,0.08)] text-foreground hover:bg-[rgba(255,255,255,0.12)]">
                  {entry.cta}
                </Button>
              ) : null}
            </article>
          ))}
        </div>
      </div>

      <div className="border-t border-border bg-[#121214] px-4 py-4">
        <div className="rounded-[var(--radius-lg)] border border-[rgba(255,255,255,0.14)] bg-[#171719] p-3">
          <input ref={fileInputRef} type="file" multiple className="hidden" onChange={handleAttachFile} />

          {attachments.length > 0 ? (
            <div className="mb-3 flex flex-wrap gap-2">
              {attachments.map(name => (
                <div key={name} className="inline-flex items-center gap-2 rounded-full border border-[rgba(255,255,255,0.12)] bg-[#0f1011] px-3 py-1 text-xs text-foreground">
                  <Paperclip className="size-3" />
                  <span>{name}</span>
                  <button type="button" onClick={() => handleRemoveAttachment(name)} className="text-[color:var(--text-secondary)] hover:text-foreground">
                    <X className="size-3" />
                  </button>
                </div>
              ))}
            </div>
          ) : null}

          <Textarea
            value={draft}
            onChange={event => setDraft(event.target.value)}
            placeholder="Attach files or continue refining the project plan."
            className="min-h-[118px] resize-none border-0 bg-transparent px-1 py-1 text-sm leading-7 text-[#f0efe9] placeholder:text-[color:var(--text-secondary)] focus-visible:border-transparent focus-visible:shadow-none"
          />

          <div className="mt-3 flex items-center justify-between gap-3 border-t border-[rgba(255,255,255,0.1)] pt-3">
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleAttachClick}
                className="inline-flex items-center gap-2 rounded-[var(--radius-sm)] px-2 py-2 text-sm text-[color:var(--text-secondary)] transition-colors hover:bg-[rgba(255,255,255,0.05)] hover:text-foreground"
              >
                <Paperclip className="size-4" />
                Attach files
              </button>
              <button
                type="button"
                onClick={handleAttachClick}
                className="inline-flex size-9 items-center justify-center rounded-[var(--radius-sm)] border border-[rgba(255,255,255,0.12)] text-[color:var(--text-secondary)] transition-colors hover:bg-[rgba(255,255,255,0.05)] hover:text-foreground"
                aria-label="Add file"
              >
                <Plus className="size-4" />
              </button>
            </div>

            <Button size="sm" onClick={handleContinue} className="h-9 px-4">
              Continue
              <SendHorizontal className="size-4" />
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
}
