import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
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
import type { NotificationEntry, NotificationStatus, Page } from "@/types";

const STATUS_VARIANT: Record<NotificationStatus, "success" | "destructive" | "warning" | "neutral"> = {
  SENT: "success",
  FAILED: "destructive",
  PENDING: "warning",
  SKIPPED: "neutral",
};

export function NotificationsPage() {
  const notificationsQuery = useQuery({
    queryKey: ["notifications"],
    queryFn: () => api.get<Page<NotificationEntry>>("/notifications", { page_size: 50 }),
    refetchInterval: 10_000,
  });

  const hasSkipped = notificationsQuery.data?.items.some((n) => n.status === "SKIPPED");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Notifications</h1>
        <p className="text-sm text-slate-500">
          Email and SMS delivery log for new-asset, critical-status and inventory-movement events.
        </p>
      </div>

      {hasSkipped && (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          Some notifications show as <strong>Skipped</strong> — either SMTP or the SMS gateway isn't
          configured on the backend (set{" "}
          <code className="rounded bg-amber-100 px-1 py-0.5 text-xs">SMTP_HOST</code> or{" "}
          <code className="rounded bg-amber-100 px-1 py-0.5 text-xs">SMS_CLIENT_ID</code> and related
          settings in <code className="rounded bg-amber-100 px-1 py-0.5 text-xs">.env</code>). The
          event is still logged; nothing is lost.
        </div>
      )}

      <Card>
        <CardContent className="p-0">
          {notificationsQuery.isLoading && (
            <div className="flex items-center gap-2 p-5 text-sm text-slate-500">
              <Spinner /> Loading notifications...
            </div>
          )}
          {notificationsQuery.data && (
            <Table>
              <TableHead>
                <TableRow>
                  <TableHeaderCell>When</TableHeaderCell>
                  <TableHeaderCell>Event</TableHeaderCell>
                  <TableHeaderCell>Channel</TableHeaderCell>
                  <TableHeaderCell>Recipient</TableHeaderCell>
                  <TableHeaderCell>Subject</TableHeaderCell>
                  <TableHeaderCell>Status</TableHeaderCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {notificationsQuery.data.items.map((n) => (
                  <TableRow key={n.id}>
                    <TableCell>{new Date(n.created_at).toLocaleString()}</TableCell>
                    <TableCell>{n.event_type}</TableCell>
                    <TableCell>
                      <Badge variant="neutral">{n.channel.toUpperCase()}</Badge>
                    </TableCell>
                    <TableCell>{n.recipient_email ?? n.recipient_phone}</TableCell>
                    <TableCell className="max-w-xs truncate" title={n.subject}>
                      {n.subject}
                    </TableCell>
                    <TableCell>
                      <Badge variant={STATUS_VARIANT[n.status]} title={n.provider_response ?? undefined}>
                        {n.status}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
                {notificationsQuery.data.items.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={6} className="py-8 text-center text-slate-400">
                      No notifications sent yet.
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
