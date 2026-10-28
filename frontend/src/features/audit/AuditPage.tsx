import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Badge, Button, Card, EmptyState, ErrorState, PageHeader, Select, Spinner, Table } from "../../components/ui";
import { api } from "../../lib/api";
import { formatDate } from "../../lib/utils";

export default function AuditPage() {
  const [outcome, setOutcome] = useState("");
  const [page, setPage] = useState(1);
  const logs = useQuery({ queryKey: ["audit", outcome, page], queryFn: () => api.audit({ outcome: outcome || undefined, page }) });
  const tone = (o: string) => (o === "success" ? "ok" : o === "denied" ? "warn" : "danger");

  return (
    <>
      <PageHeader title="Audit Logs" description="Append-only record of security-relevant events. Passwords, tokens and document contents are never stored here." />
      <Card action={
        <Select aria-label="Outcome filter" value={outcome} onChange={(e) => { setOutcome(e.target.value); setPage(1); }} className="max-w-[10rem]">
          <option value="">All outcomes</option><option>success</option><option>failure</option><option>denied</option>
        </Select>}>
        {logs.isLoading ? <Spinner label="Loading audit events" /> : logs.error ? <ErrorState error={logs.error} onRetry={() => void logs.refetch()} /> :
          logs.data!.length === 0 ? <EmptyState title="No audit events match" /> : (
            <>
              <Table head={["Time", "Action", "Outcome", "Actor", "Target", "Request ID", "Detail"]}>
                {logs.data!.map((e) => (
                  <tr key={e.id}>
                    <td className="whitespace-nowrap px-3 py-2 text-muted">{formatDate(e.created_at)}</td>
                    <td className="px-3 py-2 font-mono text-xs">{e.action}</td>
                    <td className="px-3 py-2"><Badge tone={tone(e.outcome)}>{e.outcome}</Badge></td>
                    <td className="px-3 py-2 font-mono text-xs text-muted">{e.actor_id?.slice(0, 8) ?? "—"}</td>
                    <td className="px-3 py-2 font-mono text-xs text-muted">{e.target_type ? `${e.target_type}:${e.target_id?.slice(0, 8)}` : "—"}</td>
                    <td className="px-3 py-2 font-mono text-xs text-muted">{e.request_id?.slice(0, 8) ?? "—"}</td>
                    <td className="px-3 py-2 text-muted">{e.detail ?? ""}</td>
                  </tr>
                ))}
              </Table>
              <div className="mt-4 flex items-center justify-end gap-3 text-sm text-muted">
                <Button variant="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button>
                <span>Page {page}</span>
                <Button variant="secondary" disabled={logs.data!.length < 50} onClick={() => setPage(page + 1)}>Next</Button>
              </div>
            </>
          )}
      </Card>
    </>
  );
}
