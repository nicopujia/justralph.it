import { useEffect } from "react";
import { Dashboard } from "./components/Dashboard";
import { WelcomePage } from "./components/WelcomePage";
import { useAuth } from "./hooks/useAuth";
import "./index.css";

export function App() {
  const { user, loading, loginWithGithub, handleCallback } = useAuth();

  // Handle GitHub OAuth callback: ?code=XXXX
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    if (!code) return;

    // Remove code from URL immediately to avoid re-processing on refresh
    const clean = window.location.pathname;
    window.history.replaceState({}, "", clean);

    handleCallback(code).catch((err) => {
      console.error("OAuth callback error:", err);
    });
  }, [handleCallback]);

  if (loading) {
    // Minimal loading state -- avoids flash of wrong page
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <span className="text-zinc-500 text-sm">Loading...</span>
      </div>
    );
  }

  if (!user) {
    return <WelcomePage onLogin={loginWithGithub} />;
  }

  return <Dashboard />;
}

export default App;
