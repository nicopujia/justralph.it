import { useEffect, useState } from "react";
import { Dashboard } from "./components/Dashboard";
import { WelcomePage } from "./components/WelcomePage";
import { useAuth } from "./hooks/useAuth";
import { useTheme } from "./hooks/useTheme";
import { ToastProvider } from "./components/Toast";
import "./index.css";

function AppInner() {
  const { user, loading, loginWithGithub, handleCallback } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const [skipped, setSkipped] = useState(false);

  // Handle GitHub OAuth callback: ?code=XXXX
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    if (!code) return;

    const clean = window.location.pathname;
    window.history.replaceState({}, "", clean);

    handleCallback(code).catch((err) => {
      console.error("OAuth callback error:", err);
    });
  }, [handleCallback]);

  if (loading) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <span className="text-[#00FF41] text-sm font-mono uppercase tracking-widest">
          INITIALIZING...<span className="animate-blink">_</span>
        </span>
      </div>
    );
  }

  if (!user && !skipped) {
    return (
      <WelcomePage
        onLogin={loginWithGithub}
        onSkip={() => setSkipped(true)}
        theme={theme}
        onThemeToggle={toggleTheme}
      />
    );
  }

  return <Dashboard theme={theme} onThemeToggle={toggleTheme} />;
}

export function App() {
  return (
    <ToastProvider>
      <AppInner />
    </ToastProvider>
  );
}

export default App;
