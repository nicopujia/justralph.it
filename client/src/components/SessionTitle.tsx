import { useState, useRef, useEffect, useCallback } from "react";
import { Pencil, Check, X } from "lucide-react";
import { API_URL } from "@/lib/config";

type SessionTitleProps = {
  sessionId: string;
  /** Current name; empty string means unnamed (falls back to hex ID). */
  name: string;
  /** Called after a successful rename with the new name. */
  onRename?: (name: string) => void;
};

/**
 * Inline-editable session title.
 * - Double-click or pencil icon activates edit mode.
 * - Enter saves; Escape cancels.
 * - Calls PATCH /api/sessions/{sessionId} on save.
 */
export function SessionTitle({ sessionId, name, onRename }: SessionTitleProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(name);
  const [saving, setSaving] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // Sync draft when name prop changes from outside
  useEffect(() => {
    if (!editing) setDraft(name);
  }, [name, editing]);

  useEffect(() => {
    if (editing) inputRef.current?.select();
  }, [editing]);

  const startEdit = useCallback(() => {
    setDraft(name);
    setEditing(true);
  }, [name]);

  const cancel = useCallback(() => {
    setEditing(false);
    setDraft(name);
  }, [name]);

  const save = useCallback(async () => {
    const trimmed = draft.trim();
    if (trimmed === name) {
      setEditing(false);
      return;
    }
    setSaving(true);
    try {
      const resp = await fetch(`${API_URL}/api/sessions/${sessionId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: trimmed }),
      });
      if (resp.ok) {
        onRename?.(trimmed);
        setEditing(false);
      }
    } finally {
      setSaving(false);
    }
  }, [draft, name, sessionId, onRename]);

  const displayName = name || sessionId.slice(0, 8);

  if (editing) {
    return (
      <span className="flex items-center gap-1">
        <input
          ref={inputRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") save();
            if (e.key === "Escape") cancel();
          }}
          placeholder={sessionId.slice(0, 8)}
          disabled={saving}
          className="text-xs font-mono bg-transparent border-b border-primary text-primary outline-none w-36 px-0.5"
          autoFocus
        />
        <button
          onClick={save}
          disabled={saving}
          title="Save"
          className="text-primary hover:opacity-70 transition-opacity disabled:opacity-40"
        >
          <Check className="size-3" />
        </button>
        <button
          onClick={cancel}
          disabled={saving}
          title="Cancel"
          className="text-muted-foreground hover:text-destructive transition-colors"
        >
          <X className="size-3" />
        </button>
      </span>
    );
  }

  return (
    <span
      className="flex items-center gap-1 group cursor-pointer"
      onDoubleClick={startEdit}
      title="Double-click to rename"
    >
      <span className="text-primary">{displayName}</span>
      <button
        onClick={startEdit}
        title="Rename session"
        className="opacity-0 group-hover:opacity-60 hover:!opacity-100 transition-opacity text-muted-foreground hover:text-primary"
      >
        <Pencil className="size-2.5" />
      </button>
    </span>
  );
}
