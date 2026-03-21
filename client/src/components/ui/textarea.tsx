import * as React from "react";

import { cn } from "@/lib/utils";

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "flex field-sizing-content min-h-24 w-full rounded-[var(--radius-md)] border border-input bg-[rgba(255,255,255,0.02)] px-4 py-3 text-[15px] leading-7 tracking-[-0.01em] text-foreground outline-none transition-[border-color,background-color,box-shadow,color] duration-200 placeholder:text-[color:var(--text-muted)] focus-visible:border-[color:var(--accent-primary)] focus-visible:focus-system aria-invalid:border-destructive disabled:cursor-not-allowed disabled:opacity-45",
        className,
      )}
      {...props}
    />
  );
}

export { Textarea };
