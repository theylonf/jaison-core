"""Screenshot utilities for capturing screen or mouse area."""

import io
from typing import Optional, Tuple
from PIL import Image

try:
    import pyautogui
    _pyautogui_available = True
except ImportError:
    pyautogui = None
    _pyautogui_available = False
    print("[WARNING] pyautogui nao esta instalado. Instale com: pip install pyautogui")

try:
    import win32gui
    import win32ui
    import win32con
    import win32api
except ImportError:
    win32gui = None
    win32ui = None
    win32con = None
    win32api = None
    print("[WARNING] pywin32 nao esta instalado. Instale com: pip install pywin32")


def capture_full_screen() -> Optional[bytes]:
    """Capture full screen and return as PNG bytes."""
    # Try to import again if it wasn't available before
    global pyautogui, _pyautogui_available
    if not _pyautogui_available:
        try:
            import pyautogui
            _pyautogui_available = True
        except ImportError:
            pass
    
    if pyautogui is None:
        print("[ERROR] pyautogui nao esta instalado. Nao e possivel capturar tela.")
        return None
    
    try:
        screenshot = pyautogui.screenshot()
        img_bytes = io.BytesIO()
        screenshot.save(img_bytes, format='PNG')
        return img_bytes.getvalue()
    except Exception as e:
        print(f"Erro ao capturar tela completa: {e}")
        return None


def capture_mouse_area(radius: int = 200) -> Optional[bytes]:
    """
    Capture area around mouse cursor.
    
    Args:
        radius: Radius in pixels around mouse cursor (default: 200)
    
    Returns:
        PNG image bytes or None if error
    """
    # Try to import again if it wasn't available before
    global pyautogui, _pyautogui_available
    if not _pyautogui_available:
        try:
            import pyautogui
            _pyautogui_available = True
        except ImportError:
            pass
    
    if pyautogui is None:
        print("[ERROR] pyautogui nao esta instalado. Nao e possivel capturar area do mouse.")
        return None
    
    try:
        # Get mouse position
        x, y = pyautogui.position()
        
        # Get screen dimensions
        screen_width, screen_height = pyautogui.size()
        
        # Calculate capture area
        left = max(0, x - radius)
        top = max(0, y - radius)
        right = min(screen_width, x + radius)
        bottom = min(screen_height, y + radius)
        
        width = right - left
        height = bottom - top
        
        # Try Windows API first (better performance) if available
        if win32gui is not None and win32ui is not None:
            try:
                # Capture using Windows API for better performance
                hwnd = win32gui.GetDesktopWindow()
                wDC = win32gui.GetWindowDC(hwnd)
                dcObj = win32ui.CreateDCFromHandle(wDC)
                cDC = dcObj.CreateCompatibleDC()
                dataBitMap = win32ui.CreateBitmap()
                dataBitMap.CreateCompatibleBitmap(dcObj, width, height)
                cDC.SelectObject(dataBitMap)
                cDC.BitBlt((0, 0), (width, height), dcObj, (left, top), win32con.SRCCOPY)
                
                # Convert to PIL Image
                bmpstr = dataBitMap.GetBitmapBits(True)
                img = Image.frombuffer(
                    'RGB',
                    (width, height),
                    bmpstr,
                    'raw',
                    'BGRX',
                    0,
                    1
                )
                
                # Cleanup
                win32gui.DeleteObject(dataBitMap.GetHandle())
                cDC.DeleteDC()
                dcObj.DeleteDC()
                win32gui.ReleaseDC(hwnd, wDC)
                
                # Convert to bytes
                img_bytes = io.BytesIO()
                img.save(img_bytes, format='PNG')
                return img_bytes.getvalue()
            except Exception as win_error:
                print(f"Erro ao usar Windows API, usando fallback pyautogui: {win_error}")
        
        # Fallback to pyautogui
        screenshot = pyautogui.screenshot(region=(left, top, right - left, bottom - top))
        img_bytes = io.BytesIO()
        screenshot.save(img_bytes, format='PNG')
        return img_bytes.getvalue()
        
    except Exception as e:
        print(f"Erro ao capturar área do mouse: {e}")
        return None


def capture_screen_or_mouse(use_mouse_area: bool = False, mouse_radius: int = 200) -> Optional[bytes]:
    """
    Capture screen or mouse area based on preference.
    
    Args:
        use_mouse_area: If True, capture area around mouse; if False, capture full screen
        mouse_radius: Radius around mouse if use_mouse_area is True
    
    Returns:
        PNG image bytes or None if error
    """
    if use_mouse_area:
        return capture_mouse_area(mouse_radius)
    else:
        return capture_full_screen()

