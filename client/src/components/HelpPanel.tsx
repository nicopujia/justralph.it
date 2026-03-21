import { useState, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { AlertTriangle, Upload, Play } from "lucide-react";
import { API_URL } from "@/lib/config";

type HelpPanelProps = {
  sessionId: string;
  taskId: string;
  onResume: () => void;
  onError?: (message: string) => void;
};

export function HelpPanel({ sessionId, taskId, onResume, onError }: HelpPanelProps) {
  const [uploading, setUploading] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState<string[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleUpload = async () => {
    const files = fileRef.current?.files;
    if (!files || files.length === 0) return;

    setUploading(true);
    const uploaded: string[] = [];
    for (const file of Array.from(files)) {
      const form = new FormData();
      form.append("file", file);
      try {
        const resp = await fetch(
          `${API_URL}/api/sessions/${sessionId}/uploads`,
          { method: "POST", body: form },
        );
        if (resp.ok) uploaded.push(file.name);
      } catch {
        // ignore individual failures
      }
    }
    setUploadedFiles((prev) => [...prev, ...uploaded]);
    setUploading(false);
    if (fileRef.current) fileRef.current.value = "";
  };

  const handleResume = async () => {
    // Close the blocking task
    const closeResp = await fetch(
      `${API_URL}/api/sessions/${sessionId}/tasks/${taskId}`,
      { method: "DELETE" },
    );
    if (!closeResp.ok) {
      onError?.("Resume failed");
      return;
    }

    // Restart the loop
    const restartResp = await fetch(
      `${API_URL}/api/sessions/${sessionId}/restart`,
      { method: "POST" },
    );
    if (restartResp.ok) {
      onResume();
    } else {
      onError?.("Resume failed");
    }
  };

  return (
    <Card className="border-amber-500 bg-amber-50 dark:bg-amber-950/20">
      <CardHeader className="pb-2 px-4 py-3">
        <CardTitle className="flex items-center gap-2 text-sm text-amber-700 dark:text-amber-400">
          <AlertTriangle className="size-4" />
          Ralph needs your help
        </CardTitle>
      </CardHeader>
      <CardContent className="px-4 pb-4 space-y-3">
        <p className="text-sm text-muted-foreground">
          Task <span className="font-mono font-medium">{taskId}</span> is blocked
          and requires human input. Upload files or provide what's needed, then
          click Resume.
        </p>

        {/* File upload */}
        <div className="flex gap-2">
          <Input ref={fileRef} type="file" multiple className="flex-1 text-sm" />
          <Button
            onClick={handleUpload}
            disabled={uploading}
            variant="outline"
            size="sm"
          >
            <Upload className="size-3.5 mr-1" />
            Upload
          </Button>
        </div>

        {uploadedFiles.length > 0 && (
          <div className="text-xs text-muted-foreground">
            Uploaded: {uploadedFiles.join(", ")}
          </div>
        )}

        {/* Resume */}
        <Button
          onClick={handleResume}
          className="w-full bg-green-600 hover:bg-green-700 text-white"
          size="sm"
        >
          <Play className="size-3.5 mr-1" />
          Resume Loop
        </Button>
      </CardContent>
    </Card>
  );
}
