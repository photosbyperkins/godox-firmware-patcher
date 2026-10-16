#!/usr/bin/env python3
"""
Godox Custom Firmware Drag-and-Drop Patcher (Windows .exe & macOS .app)
=======================================================================
Supports:
  1. Dragging a Godox OEM `.bin` file directly into the application window
     (native Win32 WM_DROPFILES on Windows + optional tkinterdnd2 on macOS/Windows).
  2. Dragging a `.bin` file onto the `.exe` or `.app` icon in Explorer/Finder
     (via `sys.argv` and macOS `::tk::mac::OpenDocument`).
  3. Clicking the drop card or "Browse..." to select a `.bin` file.
  4. Headless CLI mode (`--tier S|R|X|R+|X+|all`).
"""

import argparse
import ctypes
import os
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Dict, List, Optional, Tuple

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

import patcher_core as core  # noqa: E402

APP_TITLE = "Godox Custom Firmware Patcher"

# Color palette (Dark Studio Theme)
BG_MAIN = "#12151a"
BG_CARD = "#1b1f27"
BG_DROP = "#202631"
BG_DROP_HOVER = "#28303e"
BG_ROW = "#161a21"
BG_ROW_SELECTED = "#261f1c"
FG_PRIMARY = "#f0f3f8"
FG_SECONDARY = "#9aa4b5"
FG_MUTED = "#687282"
ACCENT_ORANGE = "#f06824"
ACCENT_GREEN = "#3fb950"
ACCENT_AMBER = "#d29922"
ACCENT_RED = "#f85149"
BORDER_SUBTLE = "#2d3442"


def enable_windows_high_dpi() -> None:
    """Enable Per-Monitor DPI awareness on Windows so fonts and widgets render crisply."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


class Win32DropTarget:
    """
    Zero-dependency native Windows Drag-and-Drop handler using shell32.DragAcceptFiles
    and subclassing the top-level HWND's WndProc for WM_DROPFILES (0x0233).
    """

    WM_DROPFILES = 0x0233
    GWL_WNDPROC = -4
    MSGFLT_ALLOW = 1

    def __init__(self, root: tk.Tk, on_files_dropped):
        self.root = root
        self.on_files_dropped = on_files_dropped
        self._old_wndproc = None
        self._wndproc_ref = None
        self._hook_hwnd = None

        if sys.platform == "win32":
            self._install()

    def _install(self) -> None:
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        shell32 = ctypes.windll.shell32

        LRESULT = ctypes.c_ssize_t
        WNDPROC = ctypes.WINFUNCTYPE(
            LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
        )

        user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, WNDPROC]
        user32.SetWindowLongPtrW.restype = ctypes.c_void_p
        user32.CallWindowProcW.argtypes = [
            ctypes.c_void_p,
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        user32.CallWindowProcW.restype = LRESULT

        shell32.DragAcceptFiles.argtypes = [wintypes.HWND, wintypes.BOOL]
        shell32.DragAcceptFiles.restype = None
        shell32.DragQueryFileW.argtypes = [
            ctypes.c_void_p,
            wintypes.UINT,
            wintypes.LPWSTR,
            wintypes.UINT,
        ]
        shell32.DragQueryFileW.restype = wintypes.UINT
        shell32.DragFinish.argtypes = [ctypes.c_void_p]
        shell32.DragFinish.restype = None

        self.root.update_idletasks()
        frame_hex = self.root.wm_frame()
        hwnd = int(frame_hex, 16) if frame_hex and frame_hex != "0x0" else self.root.winfo_id()
        self._hook_hwnd = hwnd

        try:
            user32.ChangeWindowMessageFilterEx.argtypes = [
                wintypes.HWND,
                wintypes.UINT,
                wintypes.DWORD,
                ctypes.c_void_p,
            ]
            user32.ChangeWindowMessageFilterEx(hwnd, self.WM_DROPFILES, self.MSGFLT_ALLOW, None)
            user32.ChangeWindowMessageFilterEx(hwnd, 0x0049, self.MSGFLT_ALLOW, None)  # WM_COPYGLOBALDATA
        except Exception:
            pass

        shell32.DragAcceptFiles(hwnd, True)

        def _wndproc(h_wnd, msg, w_param, l_param):
            if msg == self.WM_DROPFILES:
                h_drop = ctypes.c_void_p(w_param)
                count = shell32.DragQueryFileW(h_drop, 0xFFFFFFFF, None, 0)
                dropped_paths: List[str] = []
                for idx in range(count):
                    length = shell32.DragQueryFileW(h_drop, idx, None, 0)
                    buf = ctypes.create_unicode_buffer(length + 1)
                    shell32.DragQueryFileW(h_drop, idx, buf, length + 1)
                    dropped_paths.append(buf.value)
                shell32.DragFinish(h_drop)
                if dropped_paths:
                    self.root.after(10, lambda paths=dropped_paths: self.on_files_dropped(paths))
                return 0
            return user32.CallWindowProcW(self._old_wndproc, h_wnd, msg, w_param, l_param)

        self._wndproc_ref = WNDPROC(_wndproc)
        self._old_wndproc = user32.SetWindowLongPtrW(hwnd, self.GWL_WNDPROC, self._wndproc_ref)


class PatcherApp:
    def __init__(self, root: tk.Tk, initial_file: Optional[str] = None):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.configure(bg=BG_MAIN)
        self.root.minsize(640, 520)
        self.root.geometry("680x580")

        self.detection: Optional[core.DetectionResult] = None
        self.selected_tier_var = tk.StringVar(value="R")
        self.output_dir_var = tk.StringVar(value="")
        # Maps tier_key ("S", "R", ..., "ALL") -> (outer_frame, [child_widgets_to_recolor])
        self._tier_cards: Dict[str, Tuple[tk.Frame, List[tk.Widget]]] = {}

        self._build_ui()
        self._setup_drag_and_drop()

        if initial_file and os.path.exists(initial_file):
            self.load_firmware_file(initial_file)

    def _build_ui(self) -> None:
        # 1. Compact Header Bar
        header = tk.Frame(self.root, bg=BG_MAIN, padx=20, pady=12)
        header.pack(fill=tk.X)

        tk.Label(
            header,
            text="GODOX FIRMWARE PATCHER",
            font=("Segoe UI", 12, "bold"),
            fg=FG_PRIMARY,
            bg=BG_MAIN,
        ).pack(side=tk.LEFT)

        tk.Label(
            header,
            text="AD600Pro II · AD200Pro II · AD100Pro II · V100N · iT30ProN",
            font=("Segoe UI", 8, "bold"),
            fg=FG_MUTED,
            bg=BG_MAIN,
        ).pack(side=tk.RIGHT, pady=2)

        # 2. Unified Firmware Drop & Detection Card
        self.top_card = tk.Frame(
            self.root,
            bg=BG_DROP,
            highlightbackground=ACCENT_ORANGE,
            highlightthickness=1,
            padx=16,
            pady=13,
            cursor="hand2",
        )
        self.top_card.pack(fill=tk.X, padx=20, pady=(0, 12))

        top_row = tk.Frame(self.top_card, bg=BG_DROP, cursor="hand2")
        top_row.pack(fill=tk.X)

        self.browse_btn = tk.Button(
            top_row,
            text="Browse .bin...",
            command=self.browse_file,
            font=("Segoe UI", 8, "bold"),
            bg=BG_CARD,
            fg=FG_PRIMARY,
            activebackground=BG_DROP_HOVER,
            activeforeground=FG_PRIMARY,
            relief=tk.FLAT,
            padx=10,
            pady=3,
            cursor="hand2",
        )
        self.browse_btn.pack(side=tk.RIGHT, padx=(8, 0))

        self.primary_drop_lbl = tk.Label(
            top_row,
            text="⬇  Drop Official Godox .BIN Firmware Here",
            font=("Segoe UI", 11, "bold"),
            fg=FG_PRIMARY,
            bg=BG_DROP,
            anchor="w",
            cursor="hand2",
        )
        self.primary_drop_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.secondary_drop_lbl = tk.Label(
            self.top_card,
            text="Or click anywhere here to browse · Automatically detects model & base version",
            font=("Segoe UI", 9),
            fg=FG_SECONDARY,
            bg=BG_DROP,
            anchor="w",
            justify=tk.LEFT,
            wraplength=600,
            cursor="hand2",
        )
        self.secondary_drop_lbl.pack(fill=tk.X, pady=(3, 0))

        for w in (self.top_card, top_row, self.primary_drop_lbl, self.secondary_drop_lbl):
            w.bind("<Button-1>", lambda _e: self.browse_file())
            w.bind("<Enter>", lambda _e: self._set_drop_hover(True))
            w.bind("<Leave>", lambda _e: self._set_drop_hover(False))

        # 3. Bottom Action Bar (packed with side=BOTTOM first so it is never clipped)
        bottom_frame = tk.Frame(self.root, bg=BG_MAIN, padx=20, pady=14)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X)

        # Output folder & status row
        meta_row = tk.Frame(bottom_frame, bg=BG_MAIN)
        meta_row.pack(fill=tk.X, pady=(0, 8))

        self.open_folder_btn = tk.Button(
            meta_row,
            text="Open Folder",
            command=self.open_output_folder,
            font=("Segoe UI", 8),
            bg=BG_CARD,
            fg=FG_SECONDARY,
            activebackground=BG_DROP_HOVER,
            activeforeground=FG_PRIMARY,
            relief=tk.FLAT,
            padx=9,
            pady=2,
            cursor="hand2",
            state=tk.DISABLED,
        )
        self.open_folder_btn.pack(side=tk.RIGHT, padx=(6, 0))

        self.change_dir_btn = tk.Button(
            meta_row,
            text="Change Folder...",
            command=self.choose_output_dir,
            font=("Segoe UI", 8),
            bg=BG_CARD,
            fg=FG_SECONDARY,
            activebackground=BG_DROP_HOVER,
            activeforeground=FG_PRIMARY,
            relief=tk.FLAT,
            padx=9,
            pady=2,
            cursor="hand2",
            state=tk.DISABLED,
        )
        self.change_dir_btn.pack(side=tk.RIGHT)

        self.status_lbl = tk.Label(
            meta_row,
            text="Output saves alongside source .bin file",
            font=("Segoe UI", 8),
            fg=FG_MUTED,
            bg=BG_MAIN,
            anchor="w",
        )
        self.status_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Full-width primary CTA button (never truncates)
        self.patch_btn = tk.Button(
            bottom_frame,
            text="Drop a Firmware File Above to Begin",
            command=self.run_patch,
            font=("Segoe UI", 10, "bold"),
            bg=BG_CARD,
            fg=FG_MUTED,
            activebackground="#d95716",
            activeforeground="#ffffff",
            disabledforeground=FG_MUTED,
            relief=tk.FLAT,
            pady=10,
            cursor="hand2",
            state=tk.DISABLED,
        )
        self.patch_btn.pack(fill=tk.X)

        # 4. Middle Section: Tier Selection List
        self.middle_frame = tk.Frame(self.root, bg=BG_MAIN, padx=20)
        self.middle_frame.pack(fill=tk.BOTH, expand=True)

        self.section_hdr = tk.Label(
            self.middle_frame,
            text="OUTPUT FIRMWARE VERSION",
            font=("Segoe UI", 8, "bold"),
            fg=FG_MUTED,
            bg=BG_MAIN,
            anchor="w",
        )
        self.section_hdr.pack(fill=tk.X, pady=(0, 6))

        self.tiers_container = tk.Frame(self.middle_frame, bg=BG_MAIN)
        self.tiers_container.pack(fill=tk.BOTH, expand=True)

        self._render_empty_tiers()

    def _set_drop_hover(self, hovering: bool) -> None:
        bg = BG_DROP_HOVER if hovering else BG_DROP
        self.top_card.configure(bg=bg)
        for child in self.top_card.winfo_children():
            if isinstance(child, tk.Frame):
                child.configure(bg=bg)
                for sub in child.winfo_children():
                    if isinstance(sub, tk.Label):
                        sub.configure(bg=bg)
            elif isinstance(child, tk.Label):
                child.configure(bg=bg)

    def _setup_drag_and_drop(self) -> None:
        if sys.platform == "win32":
            self._win32_drop = Win32DropTarget(self.root, self._on_dropped_files)

        if sys.platform == "darwin":
            try:
                self.root.createcommand("::tk::mac::OpenDocument", self._on_mac_open_document)
            except Exception:
                pass

        if hasattr(self.root, "drop_target_register") and hasattr(self.root, "dnd_bind"):
            try:
                self.root.drop_target_register("DND_Files")
                self.root.dnd_bind("<<Drop>>", self._on_tkdnd_drop)
            except Exception:
                pass

    def _on_mac_open_document(self, *args: str) -> None:
        if args:
            self.load_firmware_file(args[0])

    def _on_tkdnd_drop(self, event) -> None:
        raw = getattr(event, "data", "")
        if not raw:
            return
        paths = self.root.tk.splitlist(raw)
        if paths:
            self._on_dropped_files(list(paths))

    def _on_dropped_files(self, paths: List[str]) -> None:
        if not paths:
            return
        bin_files = [p for p in paths if p.lower().endswith(".bin")]
        chosen = bin_files[0] if bin_files else paths[0]
        self.load_firmware_file(chosen)

    def browse_file(self) -> None:
        file_path = filedialog.askopenfilename(
            parent=self.root,
            title="Select Godox OEM Firmware (.bin)",
            filetypes=[("Firmware Binary (*.bin)", "*.bin"), ("All Files (*.*)", "*.*")],
        )
        if file_path:
            self.load_firmware_file(file_path)

    def choose_output_dir(self) -> None:
        initial = self.output_dir_var.get() or os.getcwd()
        folder = filedialog.askdirectory(
            parent=self.root,
            title="Select Output Folder for Patched Firmware",
            initialdir=initial,
        )
        if folder:
            self.output_dir_var.set(folder)
            self.status_lbl.configure(text=f"Saves to: {folder}", fg=FG_SECONDARY)

    def _render_empty_tiers(self, placeholder_text: Optional[str] = None) -> None:
        for child in self.tiers_container.winfo_children():
            child.destroy()
        self._tier_cards.clear()

        msg = placeholder_text or (
            "Supported official OEM firmware files:\n\n"
            "•  Godox AD600Pro II   (AD600PROII_v1.08.bin)\n"
            "•  Godox AD200Pro II   (AD200ProII_V1.05.bin)\n"
            "•  Godox AD100Pro II   (AD100ProII_RF433V1_07.bin)\n"
            "•  Godox V100N         (V100N_V1.04.bin)\n"
            "•  Godox iT30ProN      (iT30ProN_V1.02.bin)"
        )

        empty_box = tk.Frame(
            self.tiers_container,
            bg=BG_CARD,
            highlightbackground=BORDER_SUBTLE,
            highlightthickness=1,
            padx=20,
            pady=24,
        )
        empty_box.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            empty_box,
            text=msg,
            font=("Segoe UI", 9),
            fg=FG_SECONDARY,
            bg=BG_CARD,
            justify=tk.LEFT,
            anchor="w",
        ).pack(fill=tk.BOTH, expand=True)

    def _create_tier_card(
        self,
        key: str,
        title_text: str,
        badge_text: str,
        subtitle_text: Optional[str] = None,
    ) -> None:
        card = tk.Frame(
            self.tiers_container,
            bg=BG_ROW,
            highlightbackground=BORDER_SUBTLE,
            highlightthickness=1,
            padx=12,
            pady=7,
            cursor="hand2",
        )
        card.pack(fill=tk.X, pady=(0, 5))

        top_line = tk.Frame(card, bg=BG_ROW, cursor="hand2")
        top_line.pack(fill=tk.X)

        rb = tk.Radiobutton(
            top_line,
            text=title_text,
            variable=self.selected_tier_var,
            value=key,
            command=self._on_tier_selected,
            font=("Segoe UI", 10, "bold"),
            fg=FG_PRIMARY,
            bg=BG_ROW,
            selectcolor=BG_ROW,
            activebackground=BG_ROW,
            activeforeground=ACCENT_ORANGE,
             highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        rb.pack(side=tk.LEFT)

        badge_lbl = tk.Label(
            top_line,
            text=badge_text,
            font=("Consolas", 9, "bold"),
            fg=ACCENT_ORANGE,
            bg=BG_ROW,
            cursor="hand2",
        )
        badge_lbl.pack(side=tk.RIGHT, padx=(8, 2))

        recolor_widgets: List[tk.Widget] = [card, top_line, rb, badge_lbl]

        if subtitle_text:
            sub_lbl = tk.Label(
                card,
                text=subtitle_text,
                font=("Segoe UI", 8),
                fg=FG_SECONDARY,
                bg=BG_ROW,
                anchor="w",
                justify=tk.LEFT,
                cursor="hand2",
            )
            sub_lbl.pack(fill=tk.X, padx=(24, 4), pady=(1, 0))
            recolor_widgets.append(sub_lbl)

        for w in recolor_widgets:
            if w is not rb:
                w.bind("<Button-1>", lambda _e, k=key: self._select_tier(k))

        self._tier_cards[key] = (card, recolor_widgets)

    def _select_tier(self, key: str) -> None:
        self.selected_tier_var.set(key)
        self._on_tier_selected()

    def _on_tier_selected(self) -> None:
        chosen = self.selected_tier_var.get()
        for key, (card, widgets) in self._tier_cards.items():
            is_sel = key == chosen
            bg = BG_ROW_SELECTED if is_sel else BG_ROW
            border = ACCENT_ORANGE if is_sel else BORDER_SUBTLE
            card.configure(bg=bg, highlightbackground=border)
            for w in widgets:
                w.configure(bg=bg)
                if isinstance(w, tk.Radiobutton):
                    w.configure(selectcolor=bg, activebackground=bg)

        if self.detection and self.detection.status == "oem_match" and self.detection.model:
            model = self.detection.model
            if chosen == "ALL":
                self.patch_btn.configure(
                    text=f"Patch All {len(model.tiers)} Firmware Versions ({model.display_name})"
                )
            else:
                tier = next((t for t in model.tiers if t.tier_key == chosen), None)
                if tier:
                    self.patch_btn.configure(
                        text=f"Patch Firmware  —  Tier {tier.tier_key}: {tier.name} ({tier.version_str})"
                    )

    def _populate_tiers(self, model: core.ModelSpec) -> None:
        for child in self.tiers_container.winfo_children():
            child.destroy()
        self._tier_cards.clear()

        default_key = "R" if any(t.tier_key == "R" for t in model.tiers) else model.tiers[0].tier_key
        self.selected_tier_var.set(default_key)

        for tier in model.tiers:
            self._create_tier_card(
                key=tier.tier_key,
                title_text=f"Tier {tier.tier_key} · {tier.name}",
                badge_text=f"v{tier.version_str}  ({tier.output_filename})",
                subtitle_text=tier.summary,
            )

        ver_range = f"{model.tiers[0].version_str} – {model.tiers[-1].version_str}"
        self._create_tier_card(
            key="ALL",
            title_text=f"All Tiers · Build all {len(model.tiers)} versions",
            badge_text=ver_range,
            subtitle_text=None,
        )

        # Dynamically adjust window height so 5-tier AD600Pro II and 2-tier V100N both fit comfortably
        target_height = 470 + len(model.tiers) * 58
        cur_w = max(self.root.winfo_width(), 680)
        self.root.geometry(f"{cur_w}x{min(target_height, 740)}")

        self._on_tier_selected()

    def load_firmware_file(self, file_path: str) -> None:
        file_path = os.path.abspath(file_path.strip().strip('"'))
        try:
            det = core.identify_firmware(file_path)
        except Exception as exc:
            messagebox.showerror("Error Reading File", str(exc), parent=self.root)
            return

        self.detection = det
        out_dir = os.path.dirname(file_path)
        self.output_dir_var.set(out_dir)
        self.open_folder_btn.configure(state=tk.NORMAL, fg=FG_PRIMARY)
        self.change_dir_btn.configure(state=tk.NORMAL, fg=FG_PRIMARY)
        self.browse_btn.configure(text="Switch File...")

        fname = os.path.basename(file_path)

        if det.status == "oem_match" and det.model is not None:
            model = det.model
            self.top_card.configure(highlightbackground=ACCENT_GREEN)
            self.primary_drop_lbl.configure(
                text=f"✓  {model.display_name}  ·  Base {model.base_version_display}",
                fg=ACCENT_GREEN,
            )
            self.secondary_drop_lbl.configure(
                text=f"{fname}   —   {model.hardware_notes}",
                fg=FG_SECONDARY,
            )
            self.section_hdr.configure(
                text=f"SELECT OUTPUT VERSION FOR {model.display_name.upper()}"
            )
            self._populate_tiers(model)
            self.patch_btn.configure(state=tk.NORMAL, bg=ACCENT_ORANGE, fg="#ffffff")
            self.status_lbl.configure(text=f"Saves to: {out_dir}", fg=FG_SECONDARY)

        elif det.status == "already_patched" and det.model is not None and det.existing_tier is not None:
            self.top_card.configure(highlightbackground=ACCENT_AMBER)
            self.primary_drop_lbl.configure(
                text=f"⚠  Already Patched: {det.model.display_name} — Tier {det.existing_tier.tier_key} ({det.existing_tier.version_str})",
                fg=ACCENT_AMBER,
            )
            self.secondary_drop_lbl.configure(text=fname, fg=FG_SECONDARY)
            self.section_hdr.configure(text="ALREADY PATCHED FIRMWARE")
            self._render_empty_tiers(det.message)
            self.patch_btn.configure(
                text=f"Drop Unpatched OEM {det.model.oem_filename} to Build",
                state=tk.DISABLED,
                bg=BG_CARD,
                fg=FG_MUTED,
            )
            self.status_lbl.configure(text="File is already a custom build.", fg=ACCENT_AMBER)

        else:
            self.top_card.configure(highlightbackground=ACCENT_RED)
            self.primary_drop_lbl.configure(
                text=f"✕  Unsupported Firmware: {fname}",
                fg=ACCENT_RED,
            )
            self.secondary_drop_lbl.configure(
                text=f"{det.file_size:,} bytes · SHA-256: {det.file_sha256[:16]}...",
                fg=FG_SECONDARY,
            )
            self.section_hdr.configure(text="DIAGNOSTICS")
            self._render_empty_tiers(det.message)
            self.patch_btn.configure(
                text="Unsupported Firmware Image",
                state=tk.DISABLED,
                bg=BG_CARD,
                fg=FG_MUTED,
            )
            self.status_lbl.configure(text="Drop an official supported OEM .bin file.", fg=ACCENT_RED)

    def run_patch(self) -> None:
        if not self.detection or self.detection.status != "oem_match" or not self.detection.model:
            return

        model = self.detection.model
        choice = self.selected_tier_var.get()
        tier_keys = [t.tier_key for t in model.tiers] if choice == "ALL" else [choice]
        out_dir = self.output_dir_var.get().strip() or os.path.dirname(self.detection.file_path)

        try:
            built_files = core.build_selected_tiers(
                source_file_path=self.detection.file_path,
                model=model,
                tier_keys=tier_keys,
                output_dir=out_dir,
            )
        except Exception as exc:
            messagebox.showerror("Patch Failed", str(exc), parent=self.root)
            self.status_lbl.configure(text=f"Error: {exc}", fg=ACCENT_RED)
            return

        if len(built_files) == 1:
            b = built_files[0]
            msg = f"✓ Saved {os.path.basename(b.output_path)} (SHA-256 verified)"
        else:
            msg = f"✓ Saved all {len(built_files)} custom firmware files to {out_dir}"

        self.status_lbl.configure(text=msg, fg=ACCENT_GREEN, font=("Segoe UI", 8, "bold"))
        self.open_folder_btn.configure(bg=ACCENT_GREEN, fg="#ffffff")
        self.root.after(2500, lambda: self.open_folder_btn.configure(bg=BG_CARD, fg=FG_PRIMARY))

    def open_output_folder(self) -> None:
        folder = self.output_dir_var.get().strip()
        if not folder or not os.path.isdir(folder):
            return
        if sys.platform == "win32":
            os.startfile(folder)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])


def run_cli(file_path: str, tier_arg: str, output_dir: Optional[str]) -> int:
    det = core.identify_firmware(file_path)
    print(det.message)
    if det.status != "oem_match" or det.model is None:
        return 1

    model = det.model
    if tier_arg.upper() == "ALL":
        tier_keys = [t.tier_key for t in model.tiers]
    else:
        tier_keys = [tier_arg.upper()]

    built = core.build_selected_tiers(file_path, model, tier_keys, output_dir)
    for b in built:
        print(f"[✓] Verified {b.tier.output_filename} -> {b.output_path}")
    return 0


def create_root_window() -> tk.Tk:
    """Create TkinterDnD.Tk if tkinterdnd2 is installed, otherwise standard tk.Tk."""
    try:
        from tkinterdnd2 import TkinterDnD  # type: ignore
        return TkinterDnD.Tk()
    except Exception:
        return tk.Tk()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Godox Custom Firmware Drag-and-Drop Patcher (GUI & CLI)"
    )
    parser.add_argument(
        "firmware_file",
        nargs="?",
        help="Optional path to a Godox OEM .bin file (e.g. dragged onto the executable)",
    )
    parser.add_argument(
        "-t",
        "--tier",
        help="Run headlessly and build specific tier (S, R, X, R+, X+, or all)",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        help="Optional output directory (defaults to same directory as input .bin)",
    )

    clean_argv = [a for a in sys.argv[1:] if not a.startswith("-psn_")]
    args = parser.parse_args(clean_argv)

    if args.tier:
        if not args.firmware_file:
            parser.error("--tier requires a firmware_file path")
        sys.exit(run_cli(args.firmware_file, args.tier, args.output_dir))

    enable_windows_high_dpi()
    root = create_root_window()
    PatcherApp(root, initial_file=args.firmware_file)
    root.mainloop()


if __name__ == "__main__":
    main()
