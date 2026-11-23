#!/usr/bin/env python3
"""MeterDigit Desktop — Excel bulk → meter JPG files."""

from __future__ import annotations

import json
import re
import sys
import threading
import zipfile
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
from openpyxl import load_workbook

# Project root (works from source and from PyInstaller bundle)
if getattr(sys, "frozen", False):
    ROOT = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    APP_DIR = Path(sys.executable).resolve().parent
else:
    ROOT = Path(__file__).resolve().parents[1]
    APP_DIR = ROOT

sys.path.insert(0, str(ROOT / "scripts"))
import generate_digits as engine  # noqa: E402


def normalize(value: object, length: int) -> tuple[str, str | None]:
    try:
        return engine.only_digits(value, length), None
    except ValueError:
        return "", "Empty / no digits"


def pick_column(headers: list[str], aliases: list[str]) -> int:
    lowered = [h.strip().lower() for h in headers]
    for alias in aliases:
        if alias in lowered:
            return lowered.index(alias)
    for i, h in enumerate(lowered):
        for alias in aliases:
            if alias in h:
                return i
    return -1


def find_header(rows_raw: list) -> tuple[int, int, int] | None:
    """Return (header_row_index, small_idx, big_idx) or None."""
    small_aliases = ["small", "small number", "small_no", "chhota"]
    big_aliases = ["big", "big number", "big_no", "odo", "odometer", "reading"]
    for r, row in enumerate(rows_raw[:30]):
        header = [str(c or "") for c in (row or ())]
        if not re.search(r"small|big|digit|number|odo", " ".join(header), re.I):
            continue
        s = pick_column(header, small_aliases)
        b = pick_column(header, big_aliases)
        if s >= 0 and b >= 0:
            return r, s, b
    return None


def parse_excel(path: Path) -> list[dict]:
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows_raw = list(ws.iter_rows(values_only=True))
    wb.close()
    if not rows_raw:
        return []

    found = find_header(rows_raw)
    if found:
        header_row, small_idx, big_idx = found
        start = header_row + 1
    else:
        start, small_idx, big_idx = 0, 0, 1

    out: list[dict] = []
    for i, row in enumerate(rows_raw[start:], start=start + 1):
        cells = list(row or ())
        small_cell = cells[small_idx] if small_idx < len(cells) else None
        big_cell = cells[big_idx] if big_idx < len(cells) else None
        small_raw = "" if small_cell is None else str(small_cell).strip()
        big_raw = "" if big_cell is None else str(big_cell).strip()
        if not small_raw and not big_raw:
            continue
        small, serr = normalize(small_cell, 6)
        big, berr = normalize(big_cell, 5)
        err = " · ".join(x for x in (serr and f"Small: {serr}", berr and f"Big: {berr}") if x)
        out.append(
            {
                "row": i,
                "small_raw": small_raw,
                "big_raw": big_raw,
                "small": small,
                "big": big,
                "ok": not err,
                "error": err,
            }
        )
    return out


class MeterDigitApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("MeterDigit Desktop")
        self.geometry("920x640")
        self.minsize(780, 520)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.excel_path: Path | None = None
        self.out_dir: Path | None = None
        self.rows: list[dict] = []
        self._busy = False

        self._build()

    def _build(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(18, 8))
        ctk.CTkLabel(
            header,
            text="MeterDigit",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color="#F3E6D2",
        ).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text="Excel → meter JPG (PSD digits + crop / tilt / shades)",
            font=ctk.CTkFont(size=14),
            text_color="#CBB89A",
        ).pack(anchor="w")

        controls = ctk.CTkFrame(self, fg_color="#1B160F", corner_radius=12)
        controls.pack(fill="x", padx=20, pady=8)

        row1 = ctk.CTkFrame(controls, fg_color="transparent")
        row1.pack(fill="x", padx=14, pady=(14, 6))
        ctk.CTkButton(
            row1, text="Choose Excel", width=140, fg_color="#D97706", hover_color="#B45309",
            command=self.choose_excel,
        ).pack(side="left", padx=(0, 8))
        self.excel_label = ctk.CTkLabel(row1, text="No Excel selected", text_color="#9D8A70")
        self.excel_label.pack(side="left")

        row2 = ctk.CTkFrame(controls, fg_color="transparent")
        row2.pack(fill="x", padx=14, pady=6)
        ctk.CTkButton(
            row2, text="Output folder", width=140, fg_color="#44403C", hover_color="#57534E",
            command=self.choose_out,
        ).pack(side="left", padx=(0, 8))
        self.out_label = ctk.CTkLabel(row2, text="No output folder", text_color="#9D8A70")
        self.out_label.pack(side="left")

        row3 = ctk.CTkFrame(controls, fg_color="transparent")
        row3.pack(fill="x", padx=14, pady=(6, 14))
        self.zip_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(row3, text="Also make ZIP", variable=self.zip_var, text_color="#E8D7BD").pack(
            side="left"
        )
        self.gen_btn = ctk.CTkButton(
            row3,
            text="Generate JPGs",
            width=160,
            fg_color="#F59E0B",
            hover_color="#D97706",
            text_color="#1A1208",
            command=self.start_generate,
        )
        self.gen_btn.pack(side="right")

        self.status = ctk.CTkLabel(self, text="Ready", text_color="#A89074", anchor="w")
        self.status.pack(fill="x", padx=24, pady=(4, 0))

        self.progress = ctk.CTkProgressBar(self, progress_color="#F59E0B")
        self.progress.pack(fill="x", padx=20, pady=8)
        self.progress.set(0)

        self.table = ctk.CTkTextbox(self, font=ctk.CTkFont(family="Consolas", size=13))
        self.table.pack(fill="both", expand=True, padx=20, pady=(4, 18))
        self.table.insert("1.0", "Excel load karo — Small / Big columns.\n")
        self.table.configure(state="disabled")

    def choose_excel(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Excel",
            filetypes=[("Excel", "*.xlsx *.xls *.csv"), ("All", "*.*")],
        )
        if not path:
            return
        self.excel_path = Path(path)
        self.excel_label.configure(text=self.excel_path.name, text_color="#F3E6D2")
        try:
            self.rows = parse_excel(self.excel_path)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Excel error", str(exc))
            self.rows = []
            return
        self._render_rows()
        ok = sum(1 for r in self.rows if r["ok"])
        self.status.configure(text=f"{len(self.rows)} rows · {ok} valid")

    def choose_out(self) -> None:
        path = filedialog.askdirectory(title="Output folder")
        if not path:
            return
        self.out_dir = Path(path)
        self.out_label.configure(text=str(self.out_dir), text_color="#F3E6D2")

    def _render_rows(self) -> None:
        self.table.configure(state="normal")
        self.table.delete("1.0", "end")
        self.table.insert("end", f"{'Row':>4}  {'Small raw → 6':<22}  {'Big raw → 5':<20}  Status\n")
        self.table.insert("end", "-" * 78 + "\n")
        for r in self.rows[:200]:
            self.table.insert(
                "end",
                f"{r['row']:>4}  {r['small_raw']:>10} → {r['small'] or '—':<6}  "
                f"{r['big_raw']:>10} → {r['big'] or '—':<5}  "
                f"{'OK' if r['ok'] else r['error']}\n",
            )
        if len(self.rows) > 200:
            self.table.insert("end", f"\n… {len(self.rows) - 200} more rows\n")
        self.table.configure(state="disabled")

    def start_generate(self) -> None:
        if self._busy:
            return
        valid = [r for r in self.rows if r["ok"]]
        if not valid:
            messagebox.showwarning("Generate", "Pehle valid Excel rows load karo.")
            return
        if not self.out_dir:
            messagebox.showwarning("Generate", "Output folder choose karo.")
            return
        if not (ROOT / "data" / "digit-cache" / "meta.json").exists() and not (
            Path(getattr(sys, "_MEIPASS", ROOT)) / "data" / "digit-cache" / "meta.json"
        ).exists():
            # engine uses its own ROOT; for frozen we set MEIPASS data
            pass

        self._busy = True
        self.gen_btn.configure(state="disabled", text="Generating…")
        self.progress.set(0)
        self.status.configure(text="Generating…")
        threading.Thread(target=self._generate_worker, args=(valid,), daemon=True).start()

    def _generate_worker(self, valid: list[dict]) -> None:
        try:
            # Point engine assets at bundled/project root
            engine.ROOT = ROOT
            engine.CACHE = ROOT / "data" / "digit-cache"
            engine.META_PATH = engine.CACHE / "meta.json"
            engine.BACKGROUND_PATH = ROOT / "data" / "meter_background.jpg"

            if not engine.BACKGROUND_PATH.exists():
                raise FileNotFoundError(f"Missing {engine.BACKGROUND_PATH}")
            if not engine.META_PATH.exists():
                raise FileNotFoundError(f"Missing digit cache: {engine.META_PATH}")

            out = self.out_dir / "meterdigit_output"
            assert out is not None
            out.mkdir(parents=True, exist_ok=True)

            # Clear previous jpgs in this run folder? keep — unique names handle collisions
            jobs = [{"row": r["row"], "small": r["small"], "big": r["big"]} for r in valid]
            jobs_path = out / "_jobs.json"
            jobs_path.write_text(json.dumps(jobs), encoding="utf-8")

            # Run engine.main via argv simulation for progress-less batch,
            # or call loop ourselves for progress updates.
            meta = engine.load_meta()
            engine.clear_runtime_caches()
            engine.preload_digit_layers(meta)
            background = __import__("PIL.Image", fromlist=["Image"]).Image.open(engine.BACKGROUND_PATH)
            engine.prepare_background(meta, background)
            base_rng = __import__("random").Random()
            zoom_cycle = ("close", "medium", "wide")
            results = []
            total = len(jobs)

            for i, row in enumerate(jobs, start=1):
                big = engine.only_digits(row.get("big"), engine.BIG_LEN)
                small = engine.only_digits(row.get("small"), engine.SMALL_LEN)
                rng = __import__("random").Random(base_rng.randint(0, 2**31 - 1))
                full = engine.compose_one(meta, big, small, background)
                angle_sign = -1 if (i % 2 == 1) else 1
                zoom_mode = zoom_cycle[(i - 1) % 3]
                styled, crop_meta = engine.sample_style_crop(
                    full, rng, angle_sign=angle_sign, zoom_mode=zoom_mode
                )
                styled, shade = engine.apply_color_variation(styled, rng, scene_index=i - 1)
                filename = engine.unique_jpg_name(out, small)
                styled.convert("RGB").save(
                    out / filename, "JPEG", quality=90, optimize=False, subsampling=2
                )
                results.append(
                    {
                        "ok": True,
                        "file": filename,
                        "small": small,
                        "big": big,
                        "shade": shade,
                        "zoom": crop_meta["zoom"],
                        "angle_dir": crop_meta["angle_dir"],
                    }
                )
                self.after(0, lambda p=i / total: self.progress.set(p))
                self.after(
                    0,
                    lambda i=i, t=total, f=filename: self.status.configure(
                        text=f"Saving {i}/{t}: {f}"
                    ),
                )
                self.after(0, lambda i=i, t=total, f=filename: self._append_log(f"Saved {i}/{t}: {f}\n"))

            (out / "manifest.json").write_text(json.dumps({"results": results}, indent=2), encoding="utf-8")
            jobs_path.unlink(missing_ok=True)

            zip_path = None
            if self.zip_var.get():
                zip_path = self.out_dir / "meterdigit_batch.zip"
                with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                    for r in results:
                        zf.write(out / r["file"], arcname=r["file"])

            msg = f"Done — {len(results)} JPG in:\n{out}"
            if zip_path:
                msg += f"\n\nZIP:\n{zip_path}"
            self.after(0, lambda: self._done_ok(msg))
        except Exception as exc:  # noqa: BLE001
            self.after(0, lambda: self._done_err(str(exc)))

    def _append_log(self, text: str) -> None:
        self.table.configure(state="normal")
        self.table.insert("end", text)
        self.table.see("end")
        self.table.configure(state="disabled")

    def _done_ok(self, msg: str) -> None:
        self._busy = False
        self.gen_btn.configure(state="normal", text="Generate JPGs")
        self.progress.set(1)
        self.status.configure(text="Done")
        messagebox.showinfo("MeterDigit", msg)

    def _done_err(self, err: str) -> None:
        self._busy = False
        self.gen_btn.configure(state="normal", text="Generate JPGs")
        self.progress.set(0)
        self.status.configure(text="Failed")
        messagebox.showerror("Generate failed", err)


def main() -> None:
    if not (ROOT / "data" / "digit-cache" / "meta.json").exists():
        print(f"Digit assets missing at {ROOT / 'data' / 'digit-cache'}", file=sys.stderr)
        sys.exit(1)
    app = MeterDigitApp()
    app.mainloop()


if __name__ == "__main__":
    main()
