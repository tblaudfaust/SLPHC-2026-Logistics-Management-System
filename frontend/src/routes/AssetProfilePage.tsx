import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, QrCode } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { ALLOWED_STATUS_TRANSITIONS, STATUS_BADGE_VARIANT, STATUS_LABEL } from "@/lib/assetStatus";
import { ApiError, api } from "@/lib/api";
import { useAuthStore } from "@/store/authStore";
import type { AssetRead, AssetStatus, AssetStatusEvent } from "@/types";

/**
 * The QR endpoint is permission-gated like every other asset endpoint, so a
 * plain <img src="..."> won't work — the browser sends that request with no
 * Authorization header. Fetch it through the authenticated api client instead
 * and hand the img tag a blob: URL.
 */
function useAuthenticatedImage(path: string | null): string | null {
  const accessToken = useAuthStore((s) => s.accessToken);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!path) return;
    let objectUrl: string | null = null;
    let cancelled = false;

    (async () => {
      try {
        const blob = await api.getBlob(path);
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setBlobUrl(objectUrl);
      } catch {
        if (!cancelled) setBlobUrl(null);
      }
    })();

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [path, accessToken]);

  return blobUrl;
}

function DetailRow({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="flex justify-between border-b border-slate-100 py-2 text-sm last:border-0">
      <span className="text-slate-500">{label}</span>
      <span className="font-medium text-slate-900">{value || "-"}</span>
    </div>
  );
}

export function AssetProfilePage() {
  const { assetId } = useParams<{ assetId: string }>();
  const queryClient = useQueryClient();
  const hasPermission = useAuthStore((s) => s.hasPermission);
  const [pendingStatus, setPendingStatus] = useState("");
  const [statusError, setStatusError] = useState<string | null>(null);

  const assetQuery = useQuery({
    queryKey: ["asset", assetId],
    queryFn: () => api.get<AssetRead>(`/assets/${assetId}`),
    enabled: !!assetId,
  });

  const journeyQuery = useQuery({
    queryKey: ["asset-journey", assetId],
    queryFn: () => api.get<AssetStatusEvent[]>(`/assets/${assetId}/journey`),
    enabled: !!assetId,
  });

  const changeStatus = useMutation({
    mutationFn: (newStatus: string) => api.post(`/assets/${assetId}/status`, { new_status: newStatus }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["asset", assetId] });
      queryClient.invalidateQueries({ queryKey: ["asset-journey", assetId] });
      queryClient.invalidateQueries({ queryKey: ["assets"] });
      setPendingStatus("");
      setStatusError(null);
    },
    onError: (err) => setStatusError(err instanceof ApiError ? err.message : "Could not change status."),
  });

  // Called unconditionally (before the early returns below) per Rules of
  // Hooks — path is null until the asset has loaded, which the hook handles.
  const qrCodeUrl = useAuthenticatedImage(assetQuery.data ? `/assets/${assetQuery.data.id}/qr-code` : null);

  if (assetQuery.isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <Spinner /> Loading asset...
      </div>
    );
  }

  if (assetQuery.isError || !assetQuery.data) {
    return <p className="text-sm text-red-600">Asset not found.</p>;
  }

  const asset = assetQuery.data;
  const availableTransitions = ALLOWED_STATUS_TRANSITIONS[asset.status] ?? [];

  return (
    <div className="space-y-6">
      <div>
        <Link to="/assets" className="mb-2 inline-flex items-center gap-1 text-sm text-brand-700 hover:underline">
          <ArrowLeft size={14} /> Back to register
        </Link>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">{asset.asset_tag}</h1>
            <p className="text-sm text-slate-500">
              {asset.category.name}
              {asset.model ? ` — ${asset.model.brand} ${asset.model.model_name}` : ""}
            </p>
          </div>
          <Badge variant={STATUS_BADGE_VARIANT[asset.status]} className="text-sm">
            {STATUS_LABEL[asset.status]}
          </Badge>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Critical Snapshot</CardTitle>
          </CardHeader>
          <CardContent>
            <DetailRow label="Current Status" value={STATUS_LABEL[asset.status]} />
            <DetailRow label="Current Location" value={asset.current_location?.name} />
            <DetailRow
              label="Current Custodian"
              value={
                asset.current_custodian
                  ? `${asset.current_custodian.first_name} ${asset.current_custodian.last_name}`
                  : null
              }
            />
            <DetailRow label="Condition" value={asset.condition} />
            <DetailRow label="Remarks" value={asset.remarks} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Identification</CardTitle>
          </CardHeader>
          <CardContent>
            <DetailRow label="Serial Number" value={asset.serial_number} />
            <DetailRow label="IMEI 1" value={asset.imei_1} />
            <DetailRow label="IMEI 2" value={asset.imei_2} />
            <DetailRow label="MAC Address" value={asset.mac_address} />
            <DetailRow label="SIM / Phone" value={asset.sim_or_phone_number} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <QrCode size={14} /> QR Code
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col items-center gap-2">
            {qrCodeUrl ? (
              <img
                src={qrCodeUrl}
                alt={`QR code for ${asset.asset_tag}`}
                className="h-32 w-32 rounded-md border border-slate-200"
              />
            ) : (
              <div className="flex h-32 w-32 items-center justify-center rounded-md border border-slate-200">
                <Spinner />
              </div>
            )}
            <p className="text-center text-xs text-slate-500">
              Scanning opens this asset's profile. Encodes the Asset ID only — brief §6.3.
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Source &amp; Procurement</CardTitle>
          </CardHeader>
          <CardContent>
            <DetailRow label="Supplier / Donor" value={asset.supplier_or_donor} />
            <DetailRow label="Procurement Batch" value={asset.procurement_batch} />
            <DetailRow label="Purchase Order" value={asset.purchase_order_ref} />
            <DetailRow label="Date Acquired" value={asset.date_acquired} />
            <DetailRow label="Date Received" value={asset.date_received} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Cost &amp; Warranty</CardTitle>
          </CardHeader>
          <CardContent>
            <DetailRow
              label="Unit Cost"
              value={asset.unit_cost != null ? `${asset.currency ?? ""} ${asset.unit_cost}` : null}
            />
            <DetailRow label="Warranty Start" value={asset.warranty_start} />
            <DetailRow label="Warranty End" value={asset.warranty_end} />
          </CardContent>
        </Card>

        {hasPermission("assets.update") && (
          <Card>
            <CardHeader>
              <CardTitle>Change Status</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {availableTransitions.length === 0 ? (
                <p className="text-sm text-slate-400">No further transitions from this status.</p>
              ) : (
                <>
                  <Select value={pendingStatus} onChange={(e) => setPendingStatus(e.target.value)}>
                    <option value="">Select new status...</option>
                    {availableTransitions.map((s: AssetStatus) => (
                      <option key={s} value={s}>
                        {STATUS_LABEL[s]}
                      </option>
                    ))}
                  </Select>
                  <Button
                    className="w-full"
                    disabled={!pendingStatus || changeStatus.isPending}
                    onClick={() => changeStatus.mutate(pendingStatus)}
                  >
                    {changeStatus.isPending ? "Updating..." : "Apply status change"}
                  </Button>
                  {statusError && <p className="text-xs text-red-600">{statusError}</p>}
                </>
              )}
            </CardContent>
          </Card>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Asset Journey</CardTitle>
        </CardHeader>
        <CardContent>
          {journeyQuery.isLoading && <Spinner />}
          <ol className="space-y-4 border-l border-slate-200 pl-4">
            {journeyQuery.data?.map((event) => (
              <li key={event.id} className="relative">
                <span className="absolute -left-[21px] top-1 h-2.5 w-2.5 rounded-full bg-brand-600" />
                <p className="text-sm font-medium text-slate-900">
                  {event.event_type.replace(/_/g, " ")}
                  {event.new_status ? ` → ${STATUS_LABEL[event.new_status as AssetStatus] ?? event.new_status}` : ""}
                </p>
                <p className="text-xs text-slate-500">
                  {new Date(event.created_at).toLocaleString()}
                  {event.performed_by ? ` · ${event.performed_by.first_name} ${event.performed_by.last_name}` : ""}
                </p>
                {event.reason && <p className="mt-1 text-xs text-slate-600">{event.reason}</p>}
              </li>
            ))}
            {journeyQuery.data?.length === 0 && (
              <p className="text-sm text-slate-400">No journey events recorded yet.</p>
            )}
          </ol>
        </CardContent>
      </Card>
    </div>
  );
}
