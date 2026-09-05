import { useQuery } from "@tanstack/react-query";

import { Card, CardContent } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "@/components/ui/table";
import { api } from "@/lib/api";
import type { AuditLogEntry, Page } from "@/types";

export function AuditPage() {
  const auditQuery = useQuery({
    queryKey: ["audit-logs"],
    queryFn: () => api.get<Page<AuditLogEntry>>("/audit", { page_size: 50 }),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Audit Log</h1>
        <p className="text-sm text-slate-500">
          Immutable system activity — who did what, when, and to which record.
        </p>
      </div>

      <Card>
        <CardContent className="p-0">
          {auditQuery.isLoading && (
            <div className="flex items-center gap-2 p-5 text-sm text-slate-500">
              <Spinner /> Loading audit log...
            </div>
          )}
          {auditQuery.data && (
            <Table>
              <TableHead>
                <TableRow>
                  <TableHeaderCell>When</TableHeaderCell>
                  <TableHeaderCell>Action</TableHeaderCell>
                  <TableHeaderCell>Entity</TableHeaderCell>
                  <TableHeaderCell>IP</TableHeaderCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {auditQuery.data.items.map((entry) => (
                  <TableRow key={entry.id}>
                    <TableCell>{new Date(entry.created_at).toLocaleString()}</TableCell>
                    <TableCell className="font-medium text-slate-900">{entry.action}</TableCell>
                    <TableCell>
                      {entry.entity_type}
                      {entry.entity_id ? ` #${entry.entity_id.slice(0, 8)}` : ""}
                    </TableCell>
                    <TableCell>{entry.ip_address ?? "-"}</TableCell>
                  </TableRow>
                ))}
                {auditQuery.data.items.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={4} className="py-8 text-center text-slate-400">
                      No audit activity recorded yet.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
