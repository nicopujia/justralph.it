import { Component, type ReactNode } from "react";
import { AlertTriangle, RotateCcw } from "lucide-react";

type ErrorBoundaryProps = {
  /** Human-readable panel name shown in the fallback UI. */
  panelName: string;
  children: ReactNode;
};

type ErrorBoundaryState = {
  hasError: boolean;
  error: Error | null;
};

/**
 * Catches render errors in a panel subtree and shows a fallback instead of a white screen.
 * Each major panel (chat, right panel, terminal) should be wrapped separately.
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  override componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error(`[ErrorBoundary:${this.props.panelName}]`, error, info.componentStack);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  override render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center h-full p-6 bg-card border border-border">
          <AlertTriangle className="size-6 text-destructive mb-3" />
          <p className="text-xs font-mono uppercase tracking-widest text-foreground mb-1">
            {this.props.panelName} crashed
          </p>
          <p className="text-[10px] font-mono text-muted-foreground text-center mb-4 max-w-[280px]">
            {this.state.error?.message ?? "An unexpected error occurred."}
          </p>
          <button
            onClick={this.handleRetry}
            className="flex items-center gap-1.5 px-3 py-1.5 border border-border text-muted-foreground hover:text-primary hover:border-primary text-[10px] font-mono uppercase tracking-wider transition-colors"
          >
            <RotateCcw className="size-3" />
            Retry
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
