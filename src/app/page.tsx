"use client";

import { useMemo, useRef, useState } from "react";
import * as XLSX from "xlsx";
import { Download, FileSpreadsheet, Loader2, Trash2, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

type PreviewRow = {
  row: number;
  smallRaw: string;
  bigRaw: string;
  small: string;
  big: string;
  ok: boolean;
  error?: string;
};

/** Avoid Excel float tails like 1025.1000000000001 → last-5 digits "00001". */
function rawNumberText(value: unknown, length: number): string {
  if (value === null || value === undefined || value === "") return "";
  if (typeof value === "number" && Number.isFinite(value)) {
    if (length === 5) return value.toFixed(1);
    if (Number.isInteger(value) || Math.abs(value - Math.round(value)) < 1e-9) {
      return String(Math.round(value));
    }
    return value.toFixed(0);
  }
  const raw = String(value).trim();
  if (/^[-+]?\d+\.\d+$/.test(raw)) {
    const num = Number(raw);
    if (!Number.isFinite(num)) return raw;
    if (length === 5) return num.toFixed(1);
    if (Math.abs(num - Math.round(num)) < 1e-9) return String(Math.round(num));
    return num.toFixed(0);
  }
  return raw;
}

function digitsOnly(value: unknown, length: number): string {
  return rawNumberText(value, length).replace(/\D/g, "");
}

function normalize(value: unknown, length: number): { value: string; error?: string } {
  const digits = digitsOnly(value, length);
  if (!digits) return { value: "", error: "Empty / no digits" };
  let next = digits;
  if (next.length < length) next = next.padStart(length, "0");
  if (next.length > length) next = next.slice(-length);
  return { value: next };
}

function pickColumn(headers: string[], aliases: string[]): number {
  const lowered = headers.map((h) => h.trim().toLowerCase());
  for (const alias of aliases) {
    const idx = lowered.indexOf(alias);
    if (idx >= 0) return idx;
  }
  // fuzzy contains
  for (let i = 0; i < lowered.length; i++) {
    for (const alias of aliases) {
      if (lowered[i].includes(alias)) return i;
    }
  }
  return -1;
}

function findHeaderRow(matrix: (string | number | null)[][]): {
  row: number;
  smallIdx: number;
  bigIdx: number;
} | null {
  const smallAliases = [
    "small",
    "small number",
    "small_no",
    "smallno",
    "chhota",
    "meter small",
  ];
  const bigAliases = [
    "big",
    "big number",
    "big_no",
    "bigno",
    "bada",
    "odo",
    "odometer",
    "reading",
  ];
  const scan = Math.min(matrix.length, 30);
  for (let r = 0; r < scan; r++) {
    const headerCells = (matrix[r] ?? []).map((c) => String(c ?? ""));
    if (!/small|big|digit|number|no\.?|odo/i.test(headerCells.join(" "))) continue;
    const smallIdx = pickColumn(headerCells, smallAliases);
    const bigIdx = pickColumn(headerCells, bigAliases);
    if (smallIdx >= 0 && bigIdx >= 0) {
      return { row: r, smallIdx, bigIdx };
    }
  }
  return null;
}

function parseSheet(file: ArrayBuffer): PreviewRow[] {
  const wb = XLSX.read(file, { type: "array", raw: true });
  const sheet = wb.Sheets[wb.SheetNames[0]];
  const matrix = XLSX.utils.sheet_to_json<(string | number | null)[]>(sheet, {
    header: 1,
    defval: "",
    blankrows: false,
    raw: true,
  });

  if (matrix.length === 0) return [];

  const found = findHeaderRow(matrix);
  let start = 0;
  let smallIdx = 0;
  let bigIdx = 1;

  if (found) {
    start = found.row + 1;
    smallIdx = found.smallIdx;
    bigIdx = found.bigIdx;
  }

  const rows: PreviewRow[] = [];
  for (let i = start; i < matrix.length; i++) {
    const line = matrix[i] ?? [];
    const smallCell = line[smallIdx] ?? "";
    const bigCell = line[bigIdx] ?? "";
    const smallRaw = String(smallCell ?? "").trim();
    const bigRaw = String(bigCell ?? "").trim();
    if (!smallRaw && !bigRaw) continue;

    const small = normalize(smallCell, 6);
    const big = normalize(bigCell, 5);
    const ok = !small.error && !big.error;
    rows.push({
      row: i + 1,
      smallRaw,
      bigRaw,
      small: small.value,
      big: big.value,
      ok,
      error: [small.error && `Small: ${small.error}`, big.error && `Big: ${big.error}`]
        .filter(Boolean)
        .join(" · "),
    });
  }
  return rows;
}

export default function HomePage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [rows, setRows] = useState<PreviewRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const validRows = useMemo(() => rows.filter((r) => r.ok), [rows]);
  const invalidCount = rows.length - validRows.length;

  async function onFile(file: File) {
    setError(null);
    setStatus(null);
    setFileName(file.name);
    try {
      const buf = await file.arrayBuffer();
      const parsed = parseSheet(buf);
      if (parsed.length === 0) {
        setRows([]);
        setError("Excel mein koi valid row nahi mili. Columns: Small, Big");
        return;
      }
      setRows(parsed);
    } catch (e) {
      setRows([]);
      setError(e instanceof Error ? e.message : "Excel read failed");
    }
  }

  function clearAll() {
    setFileName(null);
    setRows([]);
    setError(null);
    setStatus(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  function generate() {
    if (validRows.length === 0) {
      setError("Generate ke liye kam se kam 1 valid row chahiye");
      return;
    }
    setError(null);
    setStatus(null);
    setPending(true);
    void (async () => {
      try {
        const res = await fetch("/api/generate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            rows: validRows.map((r) => ({
              row: r.row,
              small: r.small,
              big: r.big,
            })),
          }),
        });

        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(data.error || `Generate failed (${res.status})`);
        }

        const ok = res.headers.get("X-Generated-Ok") ?? String(validRows.length);
        const failed = res.headers.get("X-Generated-Failed") ?? "0";
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `meter_batch_${ok}_files.zip`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        setStatus(`${ok} meter files ZIP mein ready. Failed: ${failed}`);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Generate failed");
      } finally {
        setPending(false);
      }
    })();
  }

  return (
    <main className="relative min-h-svh overflow-hidden">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,_#2a1a0a_0%,_#0c0b0a_45%,_#070706_100%)]" />
      <div className="pointer-events-none absolute inset-0 opacity-[0.08] [background-image:linear-gradient(rgba(255,180,80,0.35)_1px,transparent_1px),linear-gradient(90deg,rgba(255,180,80,0.25)_1px,transparent_1px)] [background-size:48px_48px]" />

      <div className="relative mx-auto flex w-full max-w-5xl flex-col gap-8 px-4 py-10 sm:px-6 sm:py-14">
        <header className="space-y-3">
          <p className="font-[family-name:var(--font-display)] text-sm tracking-[0.28em] text-amber-500/90 uppercase">
            Conveyance · Digit Batch
          </p>
          <h1 className="font-[family-name:var(--font-display)] text-4xl leading-none text-[#f3e6d2] sm:text-5xl">
            MeterDigit
          </h1>
          <p className="max-w-2xl text-base text-[#cbb89a]/90 sm:text-lg">
            Excel se Small (6) aur Big (5) numbers upload karo — har row ki alag
            meter JPG (sample-style crop + colour).
          </p>
        </header>

        <Card className="border-[#3a2c1c]/80 bg-[#14110e]/85 text-[#f3e6d2] shadow-[0_20px_60px_rgba(0,0,0,0.45)] backdrop-blur">
          <CardHeader className="gap-2">
            <CardTitle className="font-[family-name:var(--font-display)] text-2xl text-[#f6ebda]">
              Excel upload
            </CardTitle>
            <CardDescription className="text-[#b9a48a]">
              Columns: <span className="text-amber-400">Small</span>,{" "}
              <span className="text-amber-400">Big</span>. Decimal values OK
              (jaise <code className="text-amber-300">0275.5</code> →{" "}
              <code className="text-amber-300">02755</code>). Output: sample-style
              JPG (random crop/colour/zoom/tilt), filename = Small number.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div
              className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-amber-700/50 bg-[#1b160f]/70 px-4 py-10 text-center transition hover:border-amber-500/70"
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                const f = e.dataTransfer.files?.[0];
                if (f) void onFile(f);
              }}
            >
              <Upload className="size-8 text-amber-500" />
              <div className="space-y-1">
                <p className="text-sm font-medium text-[#f3e6d2]">
                  .xlsx / .xls / .csv yahan drop karo
                </p>
                <p className="text-xs text-[#9d8a70]">
                  Ya file choose karo · max 2000 rows
                </p>
              </div>
              <div className="flex flex-wrap items-center justify-center gap-2">
                <Button
                  type="button"
                  onClick={() => inputRef.current?.click()}
                  className="bg-amber-600 text-[#1a1208] hover:bg-amber-500"
                >
                  <FileSpreadsheet className="size-4" />
                  Choose Excel
                </Button>
                <a
                  href="/samples/sample_digits.xlsx"
                  download
                  className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-amber-800/60 bg-transparent px-2.5 text-sm font-medium text-amber-200 hover:bg-amber-950/40"
                >
                  Sample Excel
                </a>
                {fileName ? (
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={clearAll}
                    className="text-[#cbb89a] hover:bg-amber-950/30 hover:text-[#f3e6d2]"
                  >
                    <Trash2 className="size-4" />
                    Clear
                  </Button>
                ) : null}
              </div>
              <input
                ref={inputRef}
                type="file"
                accept=".xlsx,.xls,.csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel,text/csv"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) void onFile(f);
                }}
              />
              {fileName ? (
                <p className="text-xs text-amber-400/90">Loaded: {fileName}</p>
              ) : null}
            </div>

            {error ? (
              <div className="rounded-lg border border-red-900/60 bg-red-950/40 px-3 py-2 text-sm text-red-200">
                {error}
              </div>
            ) : null}
            {status ? (
              <div className="rounded-lg border border-emerald-900/50 bg-emerald-950/30 px-3 py-2 text-sm text-emerald-200">
                {status}
              </div>
            ) : null}

            {rows.length > 0 ? (
              <div className="space-y-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge className="bg-amber-700/30 text-amber-200 hover:bg-amber-700/30">
                    {rows.length} rows
                  </Badge>
                  <Badge className="bg-emerald-800/30 text-emerald-200 hover:bg-emerald-800/30">
                    {validRows.length} valid
                  </Badge>
                  {invalidCount > 0 ? (
                    <Badge className="bg-red-900/40 text-red-200 hover:bg-red-900/40">
                      {invalidCount} invalid
                    </Badge>
                  ) : null}
                  <div className="ml-auto">
                    <Button
                      type="button"
                      disabled={pending || validRows.length === 0}
                      onClick={generate}
                      className="bg-amber-500 text-[#1a1208] hover:bg-amber-400"
                    >
                      {pending ? (
                        <Loader2 className="size-4 animate-spin" />
                      ) : (
                        <Download className="size-4" />
                      )}
                      {pending
                        ? "Generating…"
                        : `Generate ${validRows.length} files → ZIP`}
                    </Button>
                  </div>
                </div>

                <div className="overflow-hidden rounded-xl border border-[#3a2c1c]/80">
                  <Table>
                    <TableHeader>
                      <TableRow className="border-[#3a2c1c] hover:bg-transparent">
                        <TableHead className="text-[#9d8a70]">Excel row</TableHead>
                        <TableHead className="text-[#9d8a70]">Small (raw → 6)</TableHead>
                        <TableHead className="text-[#9d8a70]">Big (raw → 5)</TableHead>
                        <TableHead className="text-[#9d8a70]">Status</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {rows.slice(0, 100).map((r) => (
                        <TableRow
                          key={r.row}
                          className="border-[#3a2c1c]/70 hover:bg-[#1d1812]/80"
                        >
                          <TableCell className="font-mono text-xs text-[#cbb89a]">
                            {r.row}
                          </TableCell>
                          <TableCell className="font-mono text-sm">
                            <span className="text-[#8f7d66]">{r.smallRaw}</span>
                            <span className="mx-2 text-[#5c4c38]">→</span>
                            <span className="text-amber-300">{r.small || "—"}</span>
                          </TableCell>
                          <TableCell className="font-mono text-sm">
                            <span className="text-[#8f7d66]">{r.bigRaw}</span>
                            <span className="mx-2 text-[#5c4c38]">→</span>
                            <span className="text-amber-300">{r.big || "—"}</span>
                          </TableCell>
                          <TableCell>
                            {r.ok ? (
                              <span className="text-emerald-400">OK</span>
                            ) : (
                              <span className="text-red-300">{r.error}</span>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                  {rows.length > 100 ? (
                    <p className="border-t border-[#3a2c1c]/70 px-3 py-2 text-xs text-[#9d8a70]">
                      Preview pehli 100 rows dikha raha hai. Generate saari valid
                      rows ke liye chalega.
                    </p>
                  ) : null}
                </div>
              </div>
            ) : null}
          </CardContent>
        </Card>

        <section className="grid gap-4 sm:grid-cols-3">
          {[
            {
              t: "Original style",
              d: "PSD se nikale hue digit layers — size, slant, glow same.",
            },
            {
              t: "Sample-style JPG",
              d: "Left/right tilt, zoom in/out, daytime shades. Name = Small no.",
            },
            {
              t: "One file / row",
              d: "ZIP mein alag JPG — bina black corner / border artifacts.",
            },
          ].map((item) => (
            <div
              key={item.t}
              className="rounded-xl border border-[#3a2c1c]/60 bg-[#120f0c]/55 p-4 backdrop-blur-sm"
            >
              <h2 className="font-[family-name:var(--font-display)] text-lg text-[#f3e6d2]">
                {item.t}
              </h2>
              <p className="mt-1 text-sm text-[#a89074]">{item.d}</p>
            </div>
          ))}
        </section>
      </div>
    </main>
  );
}
