import { useState, useEffect, useCallback } from "react";
import { API_URL } from "@/lib/config";

type User = {
  login: string;
  name: string;
  avatar_url: string;
};

type AuthState = {
  user: User | null;
  token: string | null;
  loading: boolean;
};

const TOKEN_KEY = "ralph_token";

export function useAuth() {
  const [state, setState] = useState<AuthState>({
    user: null,
    token: null,
    loading: true,
  });

  // Validate stored token against /api/auth/me
  useEffect(() => {
    const stored = localStorage.getItem(TOKEN_KEY);
    if (!stored) {
      setState({ user: null, token: null, loading: false });
      return;
    }
    fetch(`${API_URL}/api/auth/me`, {
      headers: { Authorization: `Bearer ${stored}` },
    })
      .then((res) => {
        if (!res.ok) throw new Error("invalid token");
        return res.json() as Promise<User>;
      })
      .then((user) => setState({ user, token: stored, loading: false }))
      .catch(() => {
        localStorage.removeItem(TOKEN_KEY);
        setState({ user: null, token: null, loading: false });
      });
  }, []);

  // Fetch OAuth URL from server and navigate to it
  const loginWithGithub = useCallback(async () => {
    const res = await fetch(`${API_URL}/api/auth/github`);
    const { url } = await res.json();
    window.location.href = url;
  }, []);

  // Exchange OAuth code for token, persist, update state
  const handleCallback = useCallback(async (code: string) => {
    const res = await fetch(
      `${API_URL}/api/auth/github/callback?code=${encodeURIComponent(code)}`
    );
    if (!res.ok) throw new Error("OAuth callback failed");
    const { token, user } = await res.json();
    localStorage.setItem(TOKEN_KEY, token);
    setState({ user, token, loading: false });
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setState({ user: null, token: null, loading: false });
  }, []);

  return { ...state, loginWithGithub, handleCallback, logout };
}
