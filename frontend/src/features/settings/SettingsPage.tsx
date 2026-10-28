import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Badge, Card, ErrorState, PageHeader, Select, Spinner, Table } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { Role } from "../../types";

export default function SettingsPage() {
  const { user, can } = useAuth();
  const qc = useQueryClient();
  const models = useQuery({ queryKey: ["system-models"], queryFn: api.systemModels, enabled: !!user });
  const users = useQuery({ queryKey: ["users"], queryFn: api.users, enabled: user?.role === "admin" });
  const setRole = useMutation({ mutationFn: ({ id, role }: { id: string; role: Role }) => api.setRole(id, role), onSuccess: () => void qc.invalidateQueries({ queryKey: ["users"] }) });
  const m = models.data;

  return (
    <>
      <PageHeader title="Settings" description="Account details, model availability and (for administrators) user roles." />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Account">
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between"><dt className="text-muted">Email</dt><dd>{user?.email}</dd></div>
            <div className="flex justify-between"><dt className="text-muted">Role</dt><dd><Badge tone="accent">{user?.role}</Badge></dd></div>
          </dl>
          <p className="mt-3 text-xs text-muted">Roles are enforced by the server. Hiding a menu item is only a convenience.</p>
        </Card>
        <Card title="AI model availability">
          {models.isLoading ? <Spinner /> : models.error ? <ErrorState error={models.error} /> : m && (
            <ul className="space-y-2 text-sm">
              <li className="flex justify-between"><span>Ollama</span><Badge tone={m.ollama_reachable ? "ok" : "danger"}>{m.ollama_reachable ? "reachable" : "unreachable"}</Badge></li>
              <li className="flex justify-between"><span>LLM <code className="text-xs text-muted">{m.llm.model}</code></span><Badge tone={m.llm.available ? "ok" : "danger"}>{m.llm.available ? "available" : "not available"}</Badge></li>
              <li className="flex justify-between"><span>Embeddings <code className="text-xs text-muted">{m.embedding.provider}: {m.embedding.model} ({m.embedding.dimensions}d)</code></span><Badge tone={m.embedding.available ? "ok" : "danger"}>{m.embedding.available ? "available" : "not available"}</Badge></li>
              <li className="flex justify-between"><span>Classifier</span><Badge tone={m.classifier.available ? "ok" : "warn"}>{m.classifier.available ? "trained" : "not trained"}</Badge></li>
              <li className="flex justify-between"><span>Entity extraction</span><span className="text-muted">rules{m.entity_extraction.spacy ? " + spaCy" : " (spaCy not installed)"}</span></li>
              {m.embedding.note && <li className="text-xs text-warn">{m.embedding.note}</li>}
            </ul>
          )}
        </Card>
        {can() && (
          <Card title="Users" className="lg:col-span-2">
            {users.isLoading ? <Spinner /> : users.error ? <ErrorState error={users.error} /> : (
              <Table head={["Email", "Name", "Role"]}>
                {users.data?.map((u) => (
                  <tr key={u.id}>
                    <td className="px-3 py-2">{u.email}</td><td className="px-3 py-2 text-muted">{u.full_name}</td>
                    <td className="px-3 py-2">
                      <Select aria-label={`Role for ${u.email}`} value={u.role} disabled={u.id === user?.id} className="max-w-[10rem]"
                        onChange={(e) => setRole.mutate({ id: u.id, role: e.target.value as Role })}>
                        <option>admin</option><option>analyst</option><option>reviewer</option>
                      </Select>
                    </td>
                  </tr>
                ))}
              </Table>
            )}
            {setRole.isError && <div className="mt-3"><ErrorState error={setRole.error} /></div>}
          </Card>
        )}
      </div>
    </>
  );
}
