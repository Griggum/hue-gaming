"""Windows foreground-window metadata and local pixel capture only."""

import ctypes
import sys
from ctypes import wintypes
from dataclasses import dataclass

import psutil


@dataclass(frozen=True)
class Window:
    handle: int
    left: int
    top: int
    width: int
    height: int


class GameWindow:
    def __init__(self, process_names):
        if sys.platform != "win32":
            raise ValueError("Minimap capture requires Windows")
        self.names = {name.casefold() for name in process_names}
        self.api = ctypes.WinDLL("user32", use_last_error=True)
        self.api.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        self.api.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        self.api.GetForegroundWindow.restype = wintypes.HWND
        self.api.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self.api.IsIconic.argtypes = [wintypes.HWND]
        self.api.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        self.api.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]

    def foreground(self):
        handle = self.api.GetForegroundWindow()
        if not handle or self.api.IsIconic(handle):
            return None
        pid = wintypes.DWORD()
        self.api.GetWindowThreadProcessId(handle, ctypes.byref(pid))
        try:
            if psutil.Process(pid.value).name().casefold() not in self.names:
                return None
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None
        rect, point = wintypes.RECT(), wintypes.POINT(0, 0)
        if not self.api.GetClientRect(handle, ctypes.byref(rect)) or not self.api.ClientToScreen(
            handle, ctypes.byref(point)
        ):
            return None
        if rect.right <= 0 or rect.bottom <= 0:
            return None
        return Window(handle, point.x, point.y, rect.right, rect.bottom)


class LocalOCR:
    def __init__(self):
        from rapidocr_onnxruntime import RapidOCR

        # This distribution bundles its ONNX models. No cloud calls or downloads.
        self.engine = RapidOCR(intra_op_num_threads=1, inter_op_num_threads=1)

    def read(self, image):
        import numpy as np
        from PIL import ImageOps

        image = ImageOps.autocontrast(image.convert("L")).convert("RGB")
        image = image.resize((image.width * 3, image.height * 3))
        result, _ = self.engine(np.asarray(image), use_det=False, use_cls=False, use_rec=True)
        if not result:
            return "", 0.0
        text, score = result[0]
        return str(text).strip(), float(score)


def capture(sct, window, calibration):
    from PIL import Image

    left, top, width, height = calibration.rectangle(window.width, window.height)
    shot = sct.grab(
        {"left": window.left + left, "top": window.top + top, "width": width, "height": height}
    )
    return Image.frombytes("RGB", shot.size, shot.rgb)


def calibrate(path, process_names, delay=5):
    import time
    import tkinter as tk

    import mss
    import yaml
    from PIL import Image, ImageTk

    from .location_ocr import Calibration

    window_source = GameWindow(process_names)
    print(f"Switch to WoW now. Capturing its visible window in {delay} seconds.", flush=True)
    time.sleep(delay)
    window = window_source.foreground()
    if window is None:
        raise ValueError("WoW must be in the foreground for calibration")
    with mss.mss() as sct:
        shot = sct.grab(
            {"left": window.left, "top": window.top, "width": window.width, "height": window.height}
        )
        frame = Image.frombytes("RGB", shot.size, shot.rgb)
    root = tk.Tk()
    root.title("Drag around ONLY the minimap location text; release to save. Esc cancels.")
    scale = min(
        1,
        (root.winfo_screenwidth() - 80) / frame.width,
        (root.winfo_screenheight() - 120) / frame.height,
    )
    preview = ImageTk.PhotoImage(
        frame.resize((int(frame.width * scale), int(frame.height * scale)))
    )
    canvas = tk.Canvas(root, width=preview.width(), height=preview.height(), highlightthickness=0)
    canvas.pack()
    canvas.create_image(0, 0, image=preview, anchor="nw")
    selection = {}
    saved = []

    def start(event):
        canvas.delete("roi")
        selection["start"] = (event.x, event.y)

    def drag(event):
        if "start" in selection:
            canvas.delete("roi")
            canvas.create_rectangle(
                *selection["start"], event.x, event.y, outline="red", width=2, tags="roi"
            )

    def finish(event):
        if "start" not in selection:
            return
        x, y = selection["start"]
        left, right = sorted((round(x / scale), round(event.x / scale)))
        top, bottom = sorted((round(y / scale), round(event.y / scale)))
        try:
            roi = Calibration(
                left=left,
                top=top,
                width=right - left,
                height=bottom - top,
                client_width=window.width,
                client_height=window.height,
            )
            roi.rectangle(window.width, window.height)
        except ValueError:
            root.title("Invalid selection. Drag a small rectangle around the location text.")
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(roi.model_dump()), encoding="utf-8")
        saved.append(roi)
        root.destroy()

    canvas.bind("<ButtonPress-1>", start)
    canvas.bind("<B1-Motion>", drag)
    canvas.bind("<ButtonRelease-1>", finish)
    root.bind("<Escape>", lambda _: root.destroy())
    root.mainloop()
    print(f"Calibration saved to {path}" if saved else "Calibration cancelled")
    if saved:
        roi = saved[0]
        crop = frame.crop((roi.left, roi.top, roi.left + roi.width, roi.top + roi.height))
        raw, confidence = LocalOCR().read(crop)
        print(f"Calibration OCR preview: {raw!r} (OCR confidence {confidence:.0%})")
