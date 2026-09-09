import * as XLSX from "xlsx";

import type { StarlinkBulkImportRow, StarlinkKitType } from "@/types";

// Recognized header aliases (case/space-insensitive) — a shipment mixes
// Fixed and Roaming kits, so unlike the generic asset bulk-import, kit type
// is read per row rather than picked once for the whole file.
const HEADER_ALIASES: Record<keyof Omit<StarlinkBulkImportRow, "row_number">, string[]> = {
  kit_type: ["kittype", "type"],
  serial_number: ["sn", "serial", "serialnumber", "serialno"],
  terminal_id: ["terminalid", "terminal"],
  router_serial_number: ["routerserial", "routerserialnumber", "routersn"],
};

function normalizeHeader(header: unknown): string {
  return String(header ?? "").toLowerCase().replace(/[^a-z0-9]/g, "");
}

function cellToString(value: unknown): string | null {
  if (value === null || value === undefined || value === "") return null;
  return String(value).trim();
}

function normalizeKitType(value: string | null): StarlinkKitType | null {
  if (!value) return null;
  const v = value.toLowerCase();
  if (v.startsWith("fix") || v === "f") return "FIXED";
  if (v.startsWith("roam") || v === "r") return "ROAMING";
  return null;
}

/** Parses one workbook's first sheet into Starlink bulk-import rows,
 * continuing the row-number count from `startRowNumber` so multiple files
 * report with one consistent running row index. A row with no recognizable
 * kit type still comes through (as `kit_type: ""`) rather than being
 * silently dropped, so the backend's validation reports it as an error the
 * user can see and fix, instead of the row just vanishing. */
export function parseStarlinkWorkbook(
  buffer: ArrayBuffer,
  startRowNumber: number,
): { rows: StarlinkBulkImportRow[]; nextRowNumber: number } {
  const workbook = XLSX.read(buffer, { type: "array" });
  const sheet = workbook.Sheets[workbook.SheetNames[0]];
  const raw: unknown[][] = XLSX.utils.sheet_to_json(sheet, { header: 1, defval: null });

  if (raw.length === 0) return { rows: [], nextRowNumber: startRowNumber };

  const headerRow = raw[0];
  const columnIndex: Partial<Record<keyof Omit<StarlinkBulkImportRow, "row_number">, number>> = {};
  headerRow.forEach((header, index) => {
    const normalized = normalizeHeader(header);
    for (const [field, aliases] of Object.entries(HEADER_ALIASES)) {
      if (aliases.includes(normalized)) {
        columnIndex[field as keyof Omit<StarlinkBulkImportRow, "row_number">] = index;
      }
    }
  });

  const rows: StarlinkBulkImportRow[] = [];
  let rowNumber = startRowNumber;

  for (let i = 1; i < raw.length; i++) {
    const dataRow = raw[i];
    rowNumber++;
    const kitTypeRaw = columnIndex.kit_type !== undefined ? cellToString(dataRow[columnIndex.kit_type]) : null;
    const serial_number =
      columnIndex.serial_number !== undefined ? cellToString(dataRow[columnIndex.serial_number]) : null;
    const terminal_id = columnIndex.terminal_id !== undefined ? cellToString(dataRow[columnIndex.terminal_id]) : null;
    const router_serial_number =
      columnIndex.router_serial_number !== undefined
        ? cellToString(dataRow[columnIndex.router_serial_number])
        : null;

    if (!kitTypeRaw && !serial_number && !terminal_id && !router_serial_number) continue; // fully blank row

    rows.push({
      row_number: rowNumber,
      kit_type: (normalizeKitType(kitTypeRaw) ?? "") as StarlinkKitType,
      serial_number,
      terminal_id,
      router_serial_number,
    });
  }

  return { rows, nextRowNumber: rowNumber + 1 };
}
