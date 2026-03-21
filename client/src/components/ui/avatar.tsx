import { useState } from "react";
import { cn } from "@/lib/utils";

type AvatarProps = {
  /** URL of the avatar image (e.g. GitHub avatar_url). */
  src?: string | null;
  /** Display name used to derive initials fallback. */
  name?: string | null;
  className?: string;
};

/** Extracts up to 2 uppercase initials from a name or login string. */
function getInitials(name: string): string {
  const parts = name.trim().split(/[\s_\-]+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

/**
 * Round avatar: shows image when src loads, falls back to initials.
 * Size is controlled by className (default: w-8 h-8).
 */
export function Avatar({ src, name, className }: AvatarProps) {
  const [imgError, setImgError] = useState(false);
  const showImage = src && !imgError;
  const initials = name ? getInitials(name) : "?";

  return (
    <span
      className={cn(
        "inline-flex items-center justify-center rounded-full overflow-hidden shrink-0 select-none",
        "w-8 h-8 text-[10px] font-bold uppercase",
        !showImage && "bg-primary text-primary-foreground",
        className,
      )}
      aria-label={name ?? undefined}
    >
      {showImage ? (
        <img
          src={src}
          alt={name ?? "avatar"}
          className="w-full h-full object-cover"
          onError={() => setImgError(true)}
        />
      ) : (
        initials
      )}
    </span>
  );
}
