import { useState, useRef } from "react";
import { Upload, Play } from "lucide-react";
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
    <div className="border-2 border-destructive bg-background font-mono">
      <div className="px-4 py-3 border-b border-destructive">
        <h2 className="text-destructive text-xs uppercase tracking-wider">RALPH NEEDS YOUR HELP</h2>
      </div>
      <div className="px-4 pb-4 pt-3 space-y-3">
        <p className="text-muted-foreground text-xs">
          Task <span className="text-amber-500">{taskId}</span> is blocked and requires human input.
          Upload files or provide what's needed, then click Resume.
        </p>

        {/* File upload */}
        <div className="flex gap-2">
          <input
            ref={fileRef}
            type="file"
            multiple
            className="flex-1 text-xs text-muted-foreground bg-background border border-border px-2 py-1 file:bg-transparent file:text-muted-foreground file:border-0 file:text-xs file:uppercase file:tracking-wider file:cursor-pointer"
          />
          <button
            onClick={handleUpload}
            disabled={uploading}
            className="border border-primary text-primary bg-transparent text-[10px] uppercase tracking-wider px-2 py-1 hover:bg-primary hover:text-primary-foreground transition-colors disabled:opacity-50 flex items-center gap-1"
          >
            <Upload className="size-3" />
            UPLOAD
          </button>
        </div>

        {uploadedFiles.length > 0 && (
          <div className="text-muted-foreground text-[10px]">
            UPLOADED: {uploadedFiles.join(", ")}
          </div>
        )}

        {/* Resume */}
        <button
          onClick={handleResume}
          className="w-full border-2 border-primary bg-transparent text-primary hover:bg-primary hover:text-primary-foreground uppercase tracking-wider text-xs py-2 transition-colors flex items-center justify-center gap-1"
        >
          <Play className="size-3" />
          RESUME LOOP
        </button>
      </div>
    </div>
  );
}
