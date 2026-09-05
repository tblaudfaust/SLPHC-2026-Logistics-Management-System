import { useMutation, useQuery } from "@tanstack/react-query";
import { FileSpreadsheet, FileText, Mail, Printer } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "@/components/ui/table";
import { useWarehouseOptions } from "@/hooks/useWarehouseOptions";
import { ApiError, api } from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  ASSET_STATUSES,
  type AssetCategory,
  type AssetListItem,
  type Page,
  type ReportDefinition,
  type ReportResult,
} from "@/types";

const STATUS_OPTIONS_BY_REPORT: Record<string, string[]> = {
  asset_status: [...ASSET_STATUSES],
  unaccounted_assets: [...ASSET_STATUSES],
  stock_transfer_accountability: ["IN_TRANSIT", "RECEIVED"],
  notification_delivery: ["PENDING", "SENT", "FAILED", "SKIPPED"],
};

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

interface FilterState {
  date_from: string;
  date_to: string;
  warehouse_id: string;
  category_id: string;
  status_filter: string;
  asset_tag: string;
  entity_type: string;
  action: string;
}

const EMPTY_FILTERS: FilterState = {
  date_from: "", date_to: "", warehouse_id: "", category_id: "", status_filter: "",
  asset_tag: "", entity_type: "", action: "",
};

export function ReportsPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [filters, setFilters] = useState<FilterState>(EMPTY_FILTERS);
  const [result, setResult] = useState<ReportResult | null>(null);
  const [resolveError, setResolveError] = useState<string | null>(null);
  const [emailDialogOpen, setEmailDialogOpen] = useState(false);

  const definitionsQuery = useQuery({
    queryKey: ["report-definitions"],
    queryFn: () => api.get<ReportDefinition[]>("/reports"),
  });
  const categoriesQuery = useQuery({
    queryKey: ["asset-categories"],
    queryFn: () => api.get<AssetCategory[]>("/asset-categories"),
  });
  const { options: warehouseOptions } = useWarehouseOptions();

  const selectedDefinition = definitionsQuery.data?.find((d) => d.id === selectedId) ?? null;

  function selectReport(def: ReportDefinition) {
    setSelectedId(def.id);
    setFilters(EMPTY_FILTERS);
    setResult(null);
    setResolveError(null);
  }

  async function buildQueryParams(): Promise<Record<string, string>> {
    const params: Record<string, string> = {};
    if (filters.date_from) params.date_from = filters.date_from;
    if (filters.date_to) params.date_to = filters.date_to;
    if (filters.warehouse_id) params.warehouse_id = filters.warehouse_id;
    if (filters.category_id) params.category_id = filters.category_id;
    if (filters.status_filter) params.status_filter = filters.status_filter;
    if (filters.entity_type) params.entity_type = filters.entity_type;
    if (filters.action) params.action = filters.action;
    if (selectedDefinition?.filters.includes("asset_id") && filters.asset_tag.trim()) {
      const matches = await api.get<Page<AssetListItem>>("/assets", {
        search: filters.asset_tag.trim(), page_size: 5,
      });
      const exact = matches.items.find(
        (a) => a.asset_tag.toLowerCase() === filters.asset_tag.trim().toLowerCase(),
      );
      const found = exact ?? matches.items[0];
      if (!found) throw new Error(`No asset found matching "${filters.asset_tag}".`);
      params.asset_id = found.id;
    }
    return params;
  }

  const generateMutation = useMutation({
    mutationFn: async () => {
      if (!selectedDefinition) throw new Error("Choose a report first.");
      const params = await buildQueryParams();
      return api.get<ReportResult>(`/reports/${selectedDefinition.id}`, params);
    },
    onSuccess: (data) => {
      setResult(data);
      setResolveError(null);
    },
    onError: (err) => {
      setResult(null);
      setResolveError(err instanceof ApiError ? err.message : err instanceof Error ? err.message : "Failed to generate report.");
    },
  });

  const exportMutation = useMutation({
    mutationFn: async (format: "pdf" | "xlsx" | "csv") => {
      if (!selectedDefinition) throw new Error("Choose a report first.");
      const params = await buildQueryParams();
      const blob = await api.getBlob(`/reports/${selectedDefinition.id}/export`, { ...params, format });
      downloadBlob(blob, `${selectedDefinition.id}.${format}`);
    },
    onError: (err) => {
      setResolveError(err instanceof ApiError ? err.message : err instanceof Error ? err.message : "Export failed.");
    },
  });

  function handlePrint() {
    window.print();
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Reports</h1>
        <p className="text-sm text-slate-500">
          Detailed accountability, logistics and audit reporting — generate on screen, print, or email
          as PDF, Excel or CSV.
        </p>
      </div>

      {definitionsQuery.isLoading && (
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Spinner /> Loading reports...
        </div>
      )}

      {definitionsQuery.data && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[280px_1fr]">
          <Card className="h-fit print:hidden">
            <CardContent className="space-y-1 p-2">
              {definitionsQuery.data.map((def) => (
                <button
                  key={def.id}
                  onClick={() => selectReport(def)}
                  className={cn(
                    "w-full rounded-md px-3 py-2 text-left text-sm",
                    def.id === selectedId ? "bg-brand-700 text-white" : "text-slate-700 hover:bg-slate-100",
                  )}
                >
                  <div className="font-medium">{def.name}</div>
                  <div className={cn("text-xs", def.id === selectedId ? "text-brand-100" : "text-slate-400")}>
                    {def.description}
                  </div>
                </button>
              ))}
            </CardContent>
          </Card>

          <div className="space-y-4">
            {!selectedDefinition && (
              <Card>
                <CardContent className="p-8 text-center text-sm text-slate-400">
                  Select a report on the left to configure filters and generate it.
                </CardContent>
              </Card>
            )}

            {selectedDefinition && (
              <Card className="print:hidden">
                <CardContent className="space-y-4 p-5">
                  <div className="flex flex-wrap gap-4">
                    {selectedDefinition.filters.includes("date_from") && (
                      <div className="w-40 space-y-1.5">
                        <Label>From</Label>
                        <Input
                          type="date"
                          value={filters.date_from}
                          onChange={(e) => setFilters((f) => ({ ...f, date_from: e.target.value }))}
                        />
                      </div>
                    )}
                    {selectedDefinition.filters.includes("date_to") && (
                      <div className="w-40 space-y-1.5">
                        <Label>To</Label>
                        <Input
                          type="date"
                          value={filters.date_to}
                          onChange={(e) => setFilters((f) => ({ ...f, date_to: e.target.value }))}
                        />
                      </div>
                    )}
                    {selectedDefinition.filters.includes("warehouse_id") && (
                      <div className="w-56 space-y-1.5">
                        <Label>Warehouse</Label>
                        <Select
                          value={filters.warehouse_id}
                          onChange={(e) => setFilters((f) => ({ ...f, warehouse_id: e.target.value }))}
                        >
                          <option value="">All warehouses</option>
                          {warehouseOptions.map((w) => (
                            <option key={w.id} value={w.id}>{w.name}</option>
                          ))}
                        </Select>
                      </div>
                    )}
                    {selectedDefinition.filters.includes("category_id") && (
                      <div className="w-56 space-y-1.5">
                        <Label>Category</Label>
                        <Select
                          value={filters.category_id}
                          onChange={(e) => setFilters((f) => ({ ...f, category_id: e.target.value }))}
                        >
                          <option value="">All categories</option>
                          {(categoriesQuery.data ?? []).map((c) => (
                            <option key={c.id} value={c.id}>{c.name}</option>
                          ))}
                        </Select>
                      </div>
                    )}
                    {selectedDefinition.filters.includes("status") && (
                      <div className="w-48 space-y-1.5">
                        <Label>Status</Label>
                        <Select
                          value={filters.status_filter}
                          onChange={(e) => setFilters((f) => ({ ...f, status_filter: e.target.value }))}
                        >
                          <option value="">Any status</option>
                          {(STATUS_OPTIONS_BY_REPORT[selectedDefinition.id] ?? []).map((s) => (
                            <option key={s} value={s}>{s}</option>
                          ))}
                        </Select>
                      </div>
                    )}
                    {selectedDefinition.filters.includes("asset_id") && (
                      <div className="w-56 space-y-1.5">
                        <Label>Asset Tag</Label>
                        <Input
                          placeholder="e.g. SLPHC26-TAB-000123"
                          value={filters.asset_tag}
                          onChange={(e) => setFilters((f) => ({ ...f, asset_tag: e.target.value }))}
                        />
                      </div>
                    )}
                    {selectedDefinition.filters.includes("entity_type") && (
                      <div className="w-48 space-y-1.5">
                        <Label>Entity type (optional)</Label>
                        <Input
                          placeholder="e.g. asset, user"
                          value={filters.entity_type}
                          onChange={(e) => setFilters((f) => ({ ...f, entity_type: e.target.value }))}
                        />
                      </div>
                    )}
                    {selectedDefinition.filters.includes("action") && (
                      <div className="w-48 space-y-1.5">
                        <Label>Action (optional)</Label>
                        <Input
                          placeholder="e.g. create, login"
                          value={filters.action}
                          onChange={(e) => setFilters((f) => ({ ...f, action: e.target.value }))}
                        />
                      </div>
                    )}
                  </div>

                  {resolveError && <p className="text-sm text-red-600">{resolveError}</p>}

                  <div className="flex flex-wrap items-center gap-2">
                    <Button onClick={() => generateMutation.mutate()} disabled={generateMutation.isPending}>
                      {generateMutation.isPending ? "Generating..." : "Generate"}
                    </Button>
                    {result && (
                      <>
                        <Button variant="secondary" onClick={handlePrint}>
                          <Printer size={16} /> Print
                        </Button>
                        <Button variant="secondary" onClick={() => exportMutation.mutate("pdf")}>
                          <FileText size={16} /> PDF
                        </Button>
                        <Button variant="secondary" onClick={() => exportMutation.mutate("xlsx")}>
                          <FileSpreadsheet size={16} /> Excel
                        </Button>
                        <Button variant="secondary" onClick={() => exportMutation.mutate("csv")}>
                          CSV
                        </Button>
                        <Button variant="secondary" onClick={() => setEmailDialogOpen(true)}>
                          <Mail size={16} /> Email
                        </Button>
                      </>
                    )}
                  </div>
                </CardContent>
              </Card>
            )}

            {result && (
              <Card className="print-area">
                <CardContent className="space-y-3 p-5">
                  <div>
                    <h2 className="text-lg font-semibold text-slate-900">{result.title}</h2>
                    <p className="text-xs text-slate-500">
                      Generated {new Date(result.generated_at).toLocaleString()} by {result.generated_by}
                      {" · "}
                      {result.row_count} row{result.row_count === 1 ? "" : "s"}
                      {result.truncated && " (truncated — refine filters to see fewer)"}
                    </p>
                    {Object.keys(result.filters_applied).length > 0 && (
                      <div className="mt-1 flex flex-wrap gap-1">
                        {Object.entries(result.filters_applied).map(([k, v]) => (
                          <Badge key={k} variant="neutral" className="text-[10px]">
                            {k}: {v}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="overflow-x-auto">
                    <Table>
                      <TableHead>
                        <TableRow>
                          {result.columns.map((c) => (
                            <TableHeaderCell key={c.key}>{c.label}</TableHeaderCell>
                          ))}
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {result.rows.map((row, i) => (
                          <TableRow key={i}>
                            {result.columns.map((c) => (
                              <TableCell key={c.key}>{row[c.key] ?? ""}</TableCell>
                            ))}
                          </TableRow>
                        ))}
                        {result.rows.length === 0 && (
                          <TableRow>
                            <TableCell colSpan={result.columns.length} className="py-8 text-center text-slate-400">
                              No records match these filters.
                            </TableCell>
                          </TableRow>
                        )}
                      </TableBody>
                    </Table>
                  </div>

                  <footer className="border-t border-slate-100 pt-3 text-center text-[10px] text-slate-400">
                    <p className="font-medium text-slate-500">Statistics Sierra Leone (Stats SL)</p>
                    <p>A.J. Momoh Street / Tower Hill, P.M.B. 595, Freetown, Sierra Leone</p>
                    <p>E: info@statistics.sl &middot; T: +232-78-208595 / 30-593333 &middot; W: www.statistics.sl</p>
                  </footer>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      )}

      {selectedDefinition && result && (
        <EmailReportDialog
          open={emailDialogOpen}
          onClose={() => setEmailDialogOpen(false)}
          reportId={selectedDefinition.id}
          reportTitle={result.title}
          buildParams={buildQueryParams}
        />
      )}
    </div>
  );
}

function EmailReportDialog({
  open,
  onClose,
  reportId,
  reportTitle,
  buildParams,
}: {
  open: boolean;
  onClose: () => void;
  reportId: string;
  reportTitle: string;
  buildParams: () => Promise<Record<string, string>>;
}) {
  const [emails, setEmails] = useState("");
  const [message, setMessage] = useState("");
  const [format, setFormat] = useState<"pdf" | "xlsx" | "csv">("pdf");

  const sendMutation = useMutation({
    mutationFn: async () => {
      const params = await buildParams();
      const recipient_emails = emails.split(",").map((e) => e.trim()).filter(Boolean);
      return api.post(`/reports/${reportId}/email`, { ...params, recipient_emails, message: message || undefined, format });
    },
    onSuccess: () => {
      setEmails("");
      setMessage("");
      onClose();
    },
  });

  return (
    <Dialog open={open} onClose={onClose} title={`Email — ${reportTitle}`}>
      <div className="space-y-4">
        <div className="space-y-1.5">
          <Label>Recipient email(s)</Label>
          <Input
            placeholder="name@statistics.sl, other@statistics.sl"
            value={emails}
            onChange={(e) => setEmails(e.target.value)}
          />
          <p className="text-xs text-slate-500">Comma-separated. Up to 20 recipients.</p>
        </div>
        <div className="space-y-1.5">
          <Label>Format</Label>
          <Select value={format} onChange={(e) => setFormat(e.target.value as "pdf" | "xlsx" | "csv")}>
            <option value="pdf">PDF</option>
            <option value="xlsx">Excel</option>
            <option value="csv">CSV</option>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>Note (optional)</Label>
          <textarea
            className="h-20 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
          />
        </div>
        {sendMutation.error instanceof ApiError && (
          <p className="text-sm text-red-600">{sendMutation.error.message}</p>
        )}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button
            onClick={() => sendMutation.mutate()}
            disabled={sendMutation.isPending || !emails.trim()}
          >
            {sendMutation.isPending ? "Sending..." : "Send"}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
