import { useMemo, useState } from "react";

import { type IssueRow } from "@/components/system/app-data";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";

const typeStyles = {
  Task: "border-[#5d5840] bg-[rgba(255,255,255,0.04)] text-[#e6ddae]",
  Feature: "border-[#2e5d44] bg-[rgba(40,92,63,0.18)] text-[#97d8b3]",
  Epic: "border-[#6b5435] bg-[rgba(107,84,53,0.18)] text-[#e6be8f]",
  Bug: "border-[#6a3d37] bg-[rgba(130,63,55,0.18)] text-[#ef9a8b]",
} as const;

const statusStyles = {
  Open: "bg-[rgba(32,99,69,0.7)] text-[#8cf0bc]",
  "In progress": "bg-[rgba(77,81,92,0.8)] text-[#e2e5ef]",
  Closed: "bg-[rgba(84,39,114,0.72)] text-[#dfb7ff]",
} as const;

const priorityStyles = {
  High: "bg-[rgba(112,86,53,0.8)] text-[#ffd68c]",
  Medium: "bg-[rgba(66,70,80,0.8)] text-[#dfe3ef]",
  Low: "bg-[rgba(42,65,78,0.8)] text-[#abd6f4]",
} as const;

export function IssuesBeadBoard({ rows }: { rows: IssueRow[] }) {
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [typeFilter, setTypeFilter] = useState<string>("all");

  const filteredRows = useMemo(() => {
    const normalized = query.trim().toLowerCase();

    return rows.filter(row => {
      const matchesQuery = !normalized || [row.id, row.type, row.title, row.status, row.assignee, row.priority].join(" ").toLowerCase().includes(normalized);
      const matchesStatus = statusFilter === "all" || row.status === statusFilter;
      const matchesType = typeFilter === "all" || row.type === typeFilter;

      return matchesQuery && matchesStatus && matchesType;
    });
  }, [query, rows, statusFilter, typeFilter]);

  return (
    <section className="overflow-hidden rounded-[var(--radius-lg)] border border-[rgba(255,255,255,0.12)] bg-[#121315]">
      <div className="border-b border-[rgba(255,255,255,0.08)] px-5 py-4">
        <div className="flex flex-wrap items-center gap-3">
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="h-10 min-w-[140px] border-[rgba(255,255,255,0.12)] bg-[rgba(255,255,255,0.03)]">
              <SelectValue placeholder="All statuses" />
            </SelectTrigger>
            <SelectContent align="start">
              <SelectItem value="all">All statuses</SelectItem>
              <SelectItem value="Open">Open</SelectItem>
              <SelectItem value="In progress">In progress</SelectItem>
              <SelectItem value="Closed">Closed</SelectItem>
            </SelectContent>
          </Select>

          <Select value={typeFilter} onValueChange={setTypeFilter}>
            <SelectTrigger className="h-10 min-w-[140px] border-[rgba(255,255,255,0.12)] bg-[rgba(255,255,255,0.03)]">
              <SelectValue placeholder="All types" />
            </SelectTrigger>
            <SelectContent align="start">
              <SelectItem value="all">All types</SelectItem>
              <SelectItem value="Task">Task</SelectItem>
              <SelectItem value="Feature">Feature</SelectItem>
              <SelectItem value="Epic">Epic</SelectItem>
              <SelectItem value="Bug">Bug</SelectItem>
            </SelectContent>
          </Select>

          <div className="min-w-[260px] flex-1">
            <Input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search issues..." className="h-10 border-[rgba(255,255,255,0.12)] bg-[rgba(255,255,255,0.03)] text-foreground placeholder:text-[color:var(--text-secondary)]" />
          </div>
        </div>
      </div>

      <div className="min-h-0 overflow-auto">
        <table className="min-w-full border-separate border-spacing-0 text-left text-sm">
          <thead className="bg-[rgba(255,255,255,0.02)] text-[#c9c6bd]">
            <tr>
              {["ID", "Type", "Title", "Status", "Assignee", "Priority"].map(label => (
                <th key={label} className="border-b border-[rgba(255,255,255,0.08)] px-5 py-4 font-medium">
                  {label}
                </th>
              ))}
            </tr>
          </thead>

          <tbody>
            {filteredRows.map(row => (
              <tr key={row.id} className="hover:bg-[rgba(255,255,255,0.025)]">
                <td className="border-b border-[rgba(255,255,255,0.08)] px-5 py-4 text-foreground">{row.id}</td>
                <td className="border-b border-[rgba(255,255,255,0.08)] px-5 py-4">
                  <span className={cn("inline-flex rounded-full border px-3 py-1 text-xs", typeStyles[row.type])}>{row.type}</span>
                </td>
                <td className="border-b border-[rgba(255,255,255,0.08)] px-5 py-4 text-[15px] text-[#f0eeea]">{row.title}</td>
                <td className="border-b border-[rgba(255,255,255,0.08)] px-5 py-4">
                  <span className={cn("inline-flex rounded-full px-3 py-1 text-xs", statusStyles[row.status])}>{row.status}</span>
                </td>
                <td className="border-b border-[rgba(255,255,255,0.08)] px-5 py-4 text-[#d2cec3]">{row.assignee}</td>
                <td className="border-b border-[rgba(255,255,255,0.08)] px-5 py-4">
                  <span className={cn("inline-flex rounded-full px-3 py-1 text-xs", priorityStyles[row.priority])}>{row.priority}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {filteredRows.length === 0 ? (
          <div className="px-5 py-10 text-center text-sm text-[color:var(--text-secondary)]">No issues match the current search.</div>
        ) : null}
      </div>
    </section>
  );
}
