import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { X } from "lucide-react";

export type ToastType = "success" | "error" | "info";

type Toast = {
  id: number;
  message: string;
  type: ToastType;
};

type ToastContextValue = {
  toast: (message: string, type: ToastType) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

const MAX_TOASTS = 3;
const AUTO_DISMISS_MS = 5000;

const TYPE_STYLES: Record<ToastType, string> = {
  success: "bg-background border-2 border-primary text-primary",
  error: "bg-background border-2 border-destructive text-destructive",
  info: "bg-background border-2 border-foreground text-foreground",
};

let nextId = 0;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  // timers keyed by toast id
  const timers = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    clearTimeout(timers.current.get(id));
    timers.current.delete(id);
  }, []);

  const toast = useCallback(
    (message: string, type: ToastType) => {
      setToasts((prev) => {
        let next = [...prev, { id: nextId++, message, type }];
        // drop oldest if over cap
        if (next.length > MAX_TOASTS) {
          const [dropped, ...rest] = next;
          clearTimeout(timers.current.get(dropped.id));
          timers.current.delete(dropped.id);
          next = rest;
        }
        return next;
      });
    },
    [],
  );

  // schedule auto-dismiss whenever toasts change
  useEffect(() => {
    for (const t of toasts) {
      if (!timers.current.has(t.id)) {
        const id = setTimeout(() => dismiss(t.id), AUTO_DISMISS_MS);
        timers.current.set(t.id, id);
      }
    }
  }, [toasts, dismiss]);

  // cleanup on unmount
  useEffect(() => {
    return () => {
      for (const timer of timers.current.values()) clearTimeout(timer);
    };
  }, []);

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      {/* Fixed stack: bottom-right */}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 pointer-events-none">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={[
              "flex items-center gap-3 px-4 py-3 text-xs",
              "font-mono uppercase tracking-wider",
              "min-w-[260px] max-w-[380px] pointer-events-auto",
              "animate-slide-in-right",
              TYPE_STYLES[t.type],
            ].join(" ")}
          >
            <span className="flex-1">{t.message}</span>
            <button
              onClick={() => dismiss(t.id)}
              className="shrink-0 opacity-80 hover:opacity-100 transition-opacity"
              aria-label="Dismiss"
            >
              <X className="size-4" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside ToastProvider");
  return ctx;
}
