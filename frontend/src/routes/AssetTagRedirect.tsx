import { useQuery } from "@tanstack/react-query";
import { Navigate, useParams } from "react-router-dom";

import { Spinner } from "@/components/ui/spinner";
import { api } from "@/lib/api";
import type { AssetRead } from "@/types";

/**
 * Landing page for a scanned QR code — the code encodes the human Asset ID
 * (brief §6.3), so this resolves it to the internal id and forwards to the
 * canonical profile route.
 */
export function AssetTagRedirect() {
  const { assetTag } = useParams<{ assetTag: string }>();

  const { data, isLoading, isError } = useQuery({
    queryKey: ["asset-by-tag", assetTag],
    queryFn: () => api.get<AssetRead>(`/assets/by-tag/${assetTag}`),
    enabled: !!assetTag,
  });

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <Spinner /> Looking up {assetTag}...
      </div>
    );
  }

  if (isError || !data) {
    return <p className="text-sm text-red-600">No asset found with tag "{assetTag}".</p>;
  }

  return <Navigate to={`/assets/${data.id}`} replace />;
}
