import { useEffect, useState } from "react";
import { Dashboard } from "./components/Dashboard";
import { WelcomePage } from "./components/WelcomePage";
import { API_URL } from "./lib/config";
import "./index.css";

type AuthState = "loading" | "unauthenticated" | "authenticated";

export function App() {
  const [authState, setAuthState] = useState<AuthState>("loading");

  useEffect(() => {
    // Grab token from OAuth callback URL if present
    const params = new URLSearchParams(window.location.search);
    const urlToken = params.get("token");
    if (urlToken) {
      localStorage.setItem("github_token", urlToken);
      // Clean token from URL without reload
      window.history.replaceState({}, "", window.location.pathname);
    }

    const token = urlToken || localStorage.getItem("github_token");
    if (!token) {
      setAuthState("unauthenticated");
      return;
    }

    // Verify token against GitHub via our backend
    fetch(`${API_URL}/api/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => {
        if (res.ok) {
          setAuthState("authenticated");
        } else {
          localStorage.removeItem("github_token");
          setAuthState("unauthenticated");
        }
      })
      .catch(() => {
        localStorage.removeItem("github_token");
        setAuthState("unauthenticated");
      });
  }, []);

  if (authState === "loading") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background text-muted-foreground">
        Loading...
      </div>
    );
  }

  if (authState === "unauthenticated") {
    return <WelcomePage />;
  }

  return <Dashboard />;
}

export default App;
