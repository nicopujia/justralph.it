import * as Tooltip from "@radix-ui/react-tooltip";

type Status = "connected" | "connecting" | "disconnected";

const DOT_COLOR: Record<Status, string> = {
  connected: "bg-green-500",
  connecting: "bg-yellow-400 animate-pulse",
  disconnected: "bg-red-500",
};

const LABEL: Record<Status, string> = {
  connected: "Connected",
  connecting: "Connecting...",
  disconnected: "Disconnected",
};

/** Small colored dot with a tooltip showing the WebSocket connection status. */
export function ConnectionStatus({ status }: { status: Status }) {
  return (
    <Tooltip.Provider delayDuration={300}>
      <Tooltip.Root>
        <Tooltip.Trigger asChild>
          <span
            aria-label={LABEL[status]}
            className={[
              "inline-block size-2 rounded-full shrink-0 cursor-default",
              DOT_COLOR[status],
            ].join(" ")}
          />
        </Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Content
            side="bottom"
            sideOffset={6}
            className="z-50 px-2 py-1 text-[10px] font-mono uppercase tracking-wider bg-card border border-border text-foreground shadow-md"
          >
            {LABEL[status]}
            <Tooltip.Arrow className="fill-border" />
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    </Tooltip.Provider>
  );
}
