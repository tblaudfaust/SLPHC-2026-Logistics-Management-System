import { useMutation, useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, FileSpreadsheet, Upload } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
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
import { ApiError, api } from "@/lib/api";
import { parseAssetWorkbook } from "@/lib/parseAssetWorkbook";
import type {
  AssetCategory,
  AssetModel,
  BulkImportResponse,
  BulkImportRow,
  LocationRecord,
  Page,
} from "@/types";

interface BulkImportDialogProps {
  open: boolean;
  onClose: () => void;
  onImported: () => void;
}

type Step = "setup" | "preview" | "done";

export function BulkImportDialog({ open, onClose, onImported }: BulkImportDialogProps) {
  const [step, setStep] = useState<Step>("setup");
  const [categoryId, setCategoryId] = useState("");
  const [modelId, setModelId] = useState("");
  const [locationId, setLocationId] = useState("");
  const [rows, setRows] = useState<BulkImportRow[]>([]);
  const [fileNames, setFileNames] = useState<string[]>([]);
  const [parseError, setParseError] = useState<string | null>(null);
  const [preview, setPreview] = useState<BulkImportResponse | null>(null);
  const [result, setResult] = useState<BulkImportResponse | null>(null);

  const categoriesQuery = useQuery({
    queryKey: ["asset-categories"],
    queryFn: () => api.get<AssetCategory[]>("/asset-categories"),
  });
  const modelsQuery = useQuery({
    queryKey: ["asset-models", categoryId],
    queryFn: () => api.get<AssetModel[]>("/asset-models", { category_id: categoryId }),
    enabled: !!categoryId,
  });
  const locationsQuery = useQuery({
    queryKey: ["locations-for-select"],
    queryFn: () => api.get<Page<LocationRecord>>("/locations", { page_size: 100 }),
  });

  const serializedCategories = (categoriesQuery.data ?? []).filter((c) => c.tracking_type === "serialized");

  function reset() {
    setStep("setup");
    setRows([]);
    setFileNames([]);
    setParseError(null);
    setPreview(null);
    setResult(null);
  }

  function handleClose() {
    reset();
    setCategoryId("");
    setModelId("");
    setLocationId("");
    onClose();
  }

  async function handleFiles(fileList: FileList | null) {
    if (!fileList || fileList.length === 0) return;
    setParseError(null);
    try {
      let allRows: BulkImportRow[] = [];
      let nextRowNumber = 2; // spreadsheet row 1 is the header
      const names: string[] = [];
      for (const file of Array.from(fileList)) {
        const buffer = await file.arrayBuffer();
        const { rows: parsed, nextRowNumber: next } = parseAssetWorkbook(buffer, nextRowNumber);
        allRows = allRows.concat(parsed);
        nextRowNumber = next;
        names.push(file.name);
      }
      setRows(allRows);
      setFileNames(names);
    } catch (err) {
      setParseError(err instanceof Error ? err.message : "Could not parse the file(s).");
    }
  }

  const previewMutation = useMutation({
    mutationFn: () =>
      api.post<BulkImportResponse>("/assets/bulk-import", {
        category_id: categoryId,
        model_id: modelId || undefined,
        current_location_id: locationId || undefined,
        commit: false,
        rows,
      }),
    onSuccess: (data) => {
      setPreview(data);
      setStep("preview");
    },
  });

  const commitMutation = useMutation({
    mutationFn: () =>
      api.post<BulkImportResponse>("/assets/bulk-import", {
        category_id: categoryId,
        model_id: modelId || undefined,
        current_location_id: locationId || undefined,
        commit: true,
        rows,
      }),
    onSuccess: (data) => {
      setResult(data);
      setStep("done");
      onImported();
    },
  });

  return (
    <Dialog open={open} onClose={handleClose} title="Bulk import assets" className="max-w-2xl">
      {step === "setup" && (
        <div className="space-y-4">
          <p className="text-sm text-slate-500">
            Upload one or more Excel files. Columns are matched by name (SN/Serial, IMEI/Primary
            SIM IMEI, Secondary IMEI, Box) — no fixed template required.
          </p>

          <div className="space-y-1.5">
            <Label htmlFor="bi_category">Category</Label>
            <Select id="bi_category" value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
              <option value="">Select a category...</option>
              {serializedCategories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} ({c.code_prefix})
                </option>
              ))}
            </Select>
          </div>

          {categoryId && (
            <div className="space-y-1.5">
              <Label htmlFor="bi_model">Model (optional, applies to all rows)</Label>
              <Select id="bi_model" value={modelId} onChange={(e) => setModelId(e.target.value)}>
                <option value="">Unspecified</option>
                {modelsQuery.data?.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.brand} {m.model_name}
                  </option>
                ))}
              </Select>
            </div>
          )}

          <div className="space-y-1.5">
            <Label htmlFor="bi_location">Initial location (optional, applies to all rows)</Label>
            <Select id="bi_location" value={locationId} onChange={(e) => setLocationId(e.target.value)}>
              <option value="">Unassigned</option>
              {locationsQuery.data?.items.map((loc) => (
                <option key={loc.id} value={loc.id}>
                  {loc.name}
                </option>
              ))}
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="bi_files">Excel file(s)</Label>
            <input
              id="bi_files"
              type="file"
              accept=".xlsx,.xls,.csv"
              multiple
              onChange={(e) => handleFiles(e.target.files)}
              className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-md file:border-0 file:bg-brand-700 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-white hover:file:bg-brand-800"
            />
            {fileNames.length > 0 && (
              <p className="flex items-center gap-1.5 text-xs text-slate-500">
                <FileSpreadsheet size={14} /> {fileNames.join(", ")} — {rows.length} row(s) parsed
              </p>
            )}
            {parseError && <p className="text-xs text-red-600">{parseError}</p>}
          </div>

          {previewMutation.error instanceof ApiError && (
            <p className="text-xs text-red-600">{previewMutation.error.message}</p>
          )}

          <Button
            className="w-full"
            disabled={!categoryId || rows.length === 0 || previewMutation.isPending}
            onClick={() => previewMutation.mutate()}
          >
            {previewMutation.isPending ? (
              <>
                <Spinner /> Validating {rows.length} rows...
              </>
            ) : (
              `Validate ${rows.length || ""} rows`
            )}
          </Button>
        </div>
      )}

      {step === "preview" && preview && (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="rounded-lg border border-slate-200 p-3">
              <p className="text-2xl font-semibold text-slate-900">{preview.total_rows}</p>
              <p className="text-xs text-slate-500">Rows uploaded</p>
            </div>
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3">
              <p className="text-2xl font-semibold text-emerald-700">{preview.valid_count}</p>
              <p className="text-xs text-emerald-700">Valid</p>
            </div>
            <div className="rounded-lg border border-red-200 bg-red-50 p-3">
              <p className="text-2xl font-semibold text-red-700">{preview.invalid_count}</p>
              <p className="text-xs text-red-700">Invalid / duplicate</p>
            </div>
          </div>

          {preview.errors.length > 0 && (
            <div className="max-h-52 overflow-y-auto rounded-md border border-slate-200">
              <Table>
                <TableHead>
                  <TableRow>
                    <TableHeaderCell>Row</TableHeaderCell>
                    <TableHeaderCell>Serial</TableHeaderCell>
                    <TableHeaderCell>Reason</TableHeaderCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {preview.errors.map((e) => (
                    <TableRow key={e.row_number}>
                      <TableCell>{e.row_number}</TableCell>
                      <TableCell>{e.serial_number ?? "-"}</TableCell>
                      <TableCell className="text-red-700">{e.reason}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              {preview.invalid_count > preview.errors.length && (
                <p className="border-t border-slate-200 px-3 py-2 text-xs text-slate-500">
                  Showing first {preview.errors.length} of {preview.invalid_count} invalid rows.
                </p>
              )}
            </div>
          )}

          {preview.valid_count === 0 ? (
            <div className="flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
              <AlertTriangle size={16} /> No valid rows to import — fix the file and try again.
            </div>
          ) : (
            <p className="text-sm text-slate-600">
              Importing will register <strong>{preview.valid_count}</strong> assets under the
              selected category. Invalid rows are skipped automatically.
            </p>
          )}

          {commitMutation.error instanceof ApiError && (
            <p className="text-xs text-red-600">{commitMutation.error.message}</p>
          )}

          <div className="flex gap-2">
            <Button variant="secondary" className="flex-1" onClick={() => setStep("setup")}>
              Back
            </Button>
            <Button
              className="flex-1"
              disabled={preview.valid_count === 0 || commitMutation.isPending}
              onClick={() => commitMutation.mutate()}
            >
              {commitMutation.isPending ? (
                <>
                  <Spinner /> Importing {preview.valid_count} assets...
                </>
              ) : (
                <>
                  <Upload size={16} /> Confirm import
                </>
              )}
            </Button>
          </div>
        </div>
      )}

      {step === "done" && result && (
        <div className="space-y-4 text-center">
          <CheckCircle2 className="mx-auto text-emerald-600" size={40} />
          <p className="text-lg font-semibold text-slate-900">{result.created_count} assets registered</p>
          {result.first_asset_tag && (
            <p className="text-sm text-slate-500">
              {result.first_asset_tag} through {result.last_asset_tag}
            </p>
          )}
          {result.invalid_count > 0 && (
            <p className="text-sm text-amber-700">{result.invalid_count} row(s) were skipped.</p>
          )}
          <Button className="w-full" onClick={handleClose}>
            Done
          </Button>
        </div>
      )}
    </Dialog>
  );
}
