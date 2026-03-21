import { Github } from "lucide-react";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "./ui/card";
import { API_URL } from "@/lib/config";

export function WelcomePage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <CardTitle className="text-3xl font-bold tracking-tight">
            justralph.it
          </CardTitle>
          <CardDescription className="text-base">
            Your AI-powered development partner
          </CardDescription>
        </CardHeader>
        <CardContent className="flex justify-center">
          <Button
            size="lg"
            className="gap-2"
            onClick={() => {
              window.location.href = `${API_URL}/api/auth/github`;
            }}
          >
            <Github className="size-5" />
            Sign in with GitHub
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
