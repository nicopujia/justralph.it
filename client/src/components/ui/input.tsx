import * as React from "react";

import { cn } from "@/lib/utils";

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "h-11 w-full min-w-0 rounded-[var(--radius-sm)] border border-input bg-[rgba(255,255,255,0.02)] px-4 py-2 text-[15px] tracking-[-0.01em] text-foreground shadow-none outline-none transition-[border-color,background-color,box-shadow,color] duration-200 file:inline-flex file:h-7 file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-[color:var(--text-muted)] disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-45",
        "focus-visible:border-[color:var(--accent-primary)] focus-visible:focus-system",
        "aria-invalid:border-destructive",
        className,
      )}
      {...props}
    />
  );
}

export { Input };
