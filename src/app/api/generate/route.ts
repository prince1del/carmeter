import { spawn } from "child_process";
import { promises as fs } from "fs";
import os from "os";
import path from "path";
import { NextRequest, NextResponse } from "next/server";
import JSZip from "jszip";

export const runtime = "nodejs";
export const maxDuration = 300;

type JobRow = {
  row?: number;
  big: string | number;
  small: string | number;
};

function runPython(jobsPath: string, outDir: string): Promise<{
  code: number;
  stdout: string;
  stderr: string;
}> {
  const script = path.join(process.cwd(), "scripts", "generate_digits.py");
  return new Promise((resolve) => {
    const child = spawn("python3", [script, "--jobs", jobsPath, "--out", outDir], {
      cwd: process.cwd(),
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (d) => {
      stdout += d.toString();
    });
    child.stderr.on("data", (d) => {
      stderr += d.toString();
    });
    child.on("close", (code) => {
      resolve({ code: code ?? 1, stdout, stderr });
    });
  });
}

export async function POST(req: NextRequest) {
  let body: { rows?: JobRow[] };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const rows = body.rows ?? [];
  if (!Array.isArray(rows) || rows.length === 0) {
    return NextResponse.json({ error: "No rows provided" }, { status: 400 });
  }
  if (rows.length > 2000) {
    return NextResponse.json(
      { error: "Maximum 2000 rows per batch" },
      { status: 400 },
    );
  }

  const tmpRoot = await fs.mkdtemp(path.join(os.tmpdir(), "digit-bulk-"));
  const jobsPath = path.join(tmpRoot, "jobs.json");
  const outDir = path.join(tmpRoot, "out");
  await fs.mkdir(outDir);
  await fs.writeFile(jobsPath, JSON.stringify(rows));

  try {
    const result = await runPython(jobsPath, outDir);
    let manifest: {
      total: number;
      ok: number;
      failed: number;
      results: Array<Record<string, unknown>>;
    } | null = null;

    try {
      const manifestRaw = await fs.readFile(
        path.join(outDir, "manifest.json"),
        "utf8",
      );
      manifest = JSON.parse(manifestRaw);
    } catch {
      return NextResponse.json(
        {
          error: "Generation failed",
          detail: result.stderr || result.stdout || "No manifest produced",
        },
        { status: 500 },
      );
    }

    if (!manifest || manifest.ok === 0) {
      return NextResponse.json(
        {
          error: "No files generated",
          manifest,
          detail: result.stderr || undefined,
        },
        { status: 422 },
      );
    }

    const zip = new JSZip();
    const files = await fs.readdir(outDir);
    for (const file of files) {
      if (!/\.(pdf|png|jpe?g)$/i.test(file)) continue;
      const buf = await fs.readFile(path.join(outDir, file));
      zip.file(file, buf);
    }
    zip.file("manifest.json", JSON.stringify(manifest, null, 2));

    const zipBuf = await zip.generateAsync({
      type: "nodebuffer",
      compression: "DEFLATE",
    });

    return new NextResponse(new Uint8Array(zipBuf), {
      status: 200,
      headers: {
        "Content-Type": "application/zip",
        "Content-Disposition": `attachment; filename="meter_batch_${Date.now()}.zip"`,
        "X-Generated-Ok": String(manifest.ok),
        "X-Generated-Failed": String(manifest.failed),
        "X-Generated-Total": String(manifest.total),
      },
    });
  } finally {
    await fs.rm(tmpRoot, { recursive: true, force: true }).catch(() => undefined);
  }
}
