"""Local Windows OCR primitives. No capture, input, persistence or network access.

Callers supply an explicitly approved image. OCR is evidence for a planner,
never authorization to click or send a message.
"""
from dataclasses import dataclass
import io


def capture_approved_window(scope):
    """Capture one WhatsApp window; caller must run this in a killable worker.

    PrintWindow does not include overlapping applications. Never fall back to a
    full-screen grab if the app refuses capture.
    """
    import ctypes
    from pathlib import Path
    from PIL import Image, ImageStat
    import win32gui
    import win32ui
    from desktop.observation import ObservationError, validate_scope

    validate_scope(scope)
    if Path(scope.executable).name.casefold() != 'whatsapp.root.exe':
        raise ObservationError('Visual reading is currently restricted to WhatsApp Desktop.')
    if win32gui.IsIconic(scope.hwnd):
        raise ObservationError('Restore WhatsApp before visual reading.')
    bounds = win32gui.GetWindowRect(scope.hwnd)
    width, height = bounds[2]-bounds[0], bounds[3]-bounds[1]
    if min(width, height) < 100 or max(width, height) > 4096:
        raise ObservationError('Unsupported window dimensions.')
    handle = win32gui.GetWindowDC(scope.hwnd)
    source = target = bitmap = old = None
    try:
        source = win32ui.CreateDCFromHandle(handle)
        target = source.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(source, width, height)
        old = target.SelectObject(bitmap)
        if not ctypes.windll.user32.PrintWindow(scope.hwnd, target.GetSafeHdc(), 2):
            raise ObservationError('WhatsApp refused local visual capture.')
        image = Image.frombuffer('RGB', (width, height), bitmap.GetBitmapBits(True),
                                 'raw', 'BGRX', 0, 1).copy()
        validate_scope(scope)
        if win32gui.GetWindowRect(scope.hwnd) != bounds:
            raise ObservationError('Window moved during capture. Read again.')
        if max(ImageStat.Stat(image).stddev) < 2:
            raise ObservationError('WhatsApp returned an empty visual capture.')
        return image
    finally:
        if old is not None and target is not None:
            target.SelectObject(old)
        if bitmap is not None:
            win32gui.DeleteObject(bitmap.GetHandle())
        if target is not None:
            target.DeleteDC()
        if source is not None:
            source.DeleteDC()
        win32gui.ReleaseDC(scope.hwnd, handle)


@dataclass(frozen=True)
class TextBox:
    text: str
    left: float
    top: float
    width: float
    height: float
    surface: str = 'unknown'


def exact_region_match(boxes, expected, region):
    """Require exactly one complete OCR line wholly within a dedicated region."""
    left, top, right, bottom = region
    normalize = lambda value: ' '.join(value.split()).casefold()
    expected = normalize(expected)
    if not expected or right <= left or bottom <= top:
        return False
    matches = [box for box in boxes
               if box.left >= left and box.top >= top
               and box.left + box.width <= right
               and box.top + box.height <= bottom
               and normalize(box.text) == expected]
    return len(matches) == 1


async def recognize(image):
    """Read a bounded PIL image using installed Windows English OCR, in memory."""
    from winrt.windows.globalization import Language
    from winrt.windows.graphics.imaging import BitmapDecoder
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream

    width, height = image.size
    if min(width, height) < 1 or max(width, height) > 4096:
        raise ValueError('OCR image must be between 1 and 4096 pixels per side.')
    engine = OcrEngine.try_create_from_language(Language('en-US'))
    if engine is None:
        raise ValueError('Install the Windows English OCR language pack first.')
    if max(width, height) > OcrEngine.max_image_dimension:
        raise ValueError('Image exceeds the Windows OCR dimension limit.')
    data = io.BytesIO()
    rgb = image.convert('RGB')
    rgb.save(data, format='PNG')
    stream = InMemoryRandomAccessStream()
    writer = DataWriter(stream)
    bitmap = None
    try:
        writer.write_bytes(data.getvalue())
        await writer.store_async()
        writer.detach_stream()
        stream.seek(0)
        decoder = await BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_async()
        result = await engine.recognize_async(bitmap)
        boxes = []
        text_budget = 16000
        for line in result.lines:
            words = list(line.words)
            if not words:
                continue
            rects = [word.bounding_rect for word in words]
            left = min(rect.x for rect in rects)
            top = min(rect.y for rect in rects)
            right = max(rect.x + rect.width for rect in rects)
            bottom = max(rect.y + rect.height for rect in rects)
            text = line.text[:min(1000, text_budget)]
            # WhatsApp's outgoing bubble uses a green background in its dark
            # theme. This is supporting evidence only; callers must also verify
            # new exact text, right alignment, header and empty composer.
            samples=[]
            for y in range(max(0,int(top)-2),min(height,int(bottom)+2),3):
                for x in range(max(0,int(left)-2),min(width,int(right)+2),5):
                    red, green, blue = rgb.getpixel((x,y))
                    samples.append(green > red+18 and green > blue+5 and green < 180)
            surface='outgoing_green' if samples and sum(samples)/len(samples)>.55 else 'unknown'
            boxes.append(TextBox(text, left, top, right-left, bottom-top, surface))
            text_budget -= len(text)
            if len(boxes) >= 200 or text_budget <= 0:
                break
        return boxes
    finally:
        rgb.close()
        if bitmap is not None:
            bitmap.close()
        writer.close()
        stream.close()
