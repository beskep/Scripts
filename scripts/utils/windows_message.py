import ctypes
import winsound


class WindowsMessage:
    WS_EX_TOPMOST = 0x40000

    @staticmethod
    def msg_beep(*, ok=True):
        if hasattr(winsound, 'MessageBeep'):
            t = winsound.MB_OK if ok else winsound.MB_ICONHAND
            winsound.MessageBeep(t)

    @classmethod
    def msg_box(cls, message: str, title: str | None = None):
        ctypes.windll.user32.MessageBoxExW(None, message, title, cls.WS_EX_TOPMOST)
