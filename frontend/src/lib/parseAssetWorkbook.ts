import * as XLSX from "xlsx";

import type { BulkImportRow } from "@/types";

// Recognized header aliases (case/space-insensitive) — covers the columns
// seen in real tablet-batch exports without requiring a fixed template.
const HEADER_ALIASES: Record<keyof Omit<BulkImportRow, "row_number">, string[]> = {
  serial_number: ["sn", "serial", "serialnumber", "serialno"],
  imei_1: ["primarysimimei", "imei1", "imei", "primaryimei"],
  imei_2: ["secondaryimei", "imei2"],
  box_number: ["boxnumber", "box", "boxno"],
};

function normalizeHeader(header: unknown): string {
  return String(header ?? "").toLowerCase().replace(/[^a-z0-9]/g, "");
}

function cellToString(value: unknown): string | null {
  if (value === null || value === undefined || value === "") return null;
  return String(value).trim();
}

/** Parses one workbook's first sheet into rows, forward-filling box_number
 * for the common "one label per box of N units" layout, and continuing the
 * row-number count from `startRowNumber` so multiple files can be reported
 * with a consistent running row index. Returns the parsed rows and the next
 * available row_number for a subsequent file. */
export function parseAssetWorkbook(
  buffer: ArrayBuffer,
  startRowNumber: number,
): { rows: BulkImportRow[]; nextRowNumber: number } {
  const workbook = XLSX.read(buffer, { type: "array" });
  const sheet = workbook.Sheets[workbook.SheetNames[0]];
  const raw: unknown[][] = XLSX.utils.sheet_to_json(sheet, { header: 1, defval: null });

  if (raw.length === 0) return { rows: [], nextRowNumber: startRowNumber };

  const headerRow = raw[0];
  const columnIndex: Partial<Record<keyof Omit<BulkImportRow, "row_number">, number>> = {};
  headerRow.forEach((header, index) => {
    const normalized = normalizeHeader(header);
    for (const [field, aliases] of Object.entries(HEADER_ALIASES)) {
      if (aliases.includes(normalized)) {
        columnIndex[field as keyof Omit<BulkImportRow, "row_number">] = index;
      }
    }
  });

  const rows: BulkImportRow[] = [];
  let lastBoxNumber: string | null = null;
  let rowNumber = startRowNumber;

  for (let i = 1; i < raw.length; i++) {
    const dataRow = raw[i];
    rowNumber++;
    const serial_number = columnIndex.serial_number !== undefined ? cellToString(dataRow[columnIndex.serial_number]) : null;
    const imei_1 = columnIndex.imei_1 !== undefined ? cellToString(dataRow[columnIndex.imei_1]) : null;
    const imei_2 = columnIndex.imei_2 !== undefined ? cellToString(dataRow[columnIndex.imei_2]) : null;
    let box_number = columnIndex.box_number !== undefined ? cellToString(dataRow[columnIndex.box_number]) : null;

    if (!serial_number && !imei_1 && !imei_2 && !box_number) continue; // fully blank row

    if (box_number) lastBoxNumber = box_number;
    else box_number = lastBoxNumber;

    rows.push({ row_number: rowNumber, serial_number, imei_1, imei_2, box_number });
  }

  return { rows, nextRowNumber: rowNumber + 1 };
}
