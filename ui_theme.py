"""
UI 主题模块：浅色/深色配色方案、Windows 系统主题检测与 ttk 样式应用
"""

import sys
import tkinter as tk
from tkinter import ttk

THEME_LIGHT = "light"
THEME_DARK = "dark"

# 配色键说明：
# bg/fg                窗口底色与默认前景文字
# field                输入类控件（下拉框）底色
# button_bg/hover/press 按钮常态、悬停、按下底色
# trough               滑条槽底色
# select_bg/select_fg  选中文字的底色/前景色
# accent               焦点高亮色
# text_bg/text_fg      日志文本框底色/前景色
# log_*                日志分级颜色
# status_*             状态栏分级颜色
LIGHT_COLORS = {
    "bg": "#f0f0f0",
    "fg": "#1f1f1f",
    "border": "#b8b8b8",
    "field": "#ffffff",
    "button_bg": "#e1e1e1",
    "button_fg": "#1f1f1f",
    "button_hover": "#d5d5d5",
    "button_press": "#c8c8c8",
    "disabled_fg": "#9c9c9c",
    "trough": "#d8d8d8",
    "select_bg": "#0078d4",
    "select_fg": "#ffffff",
    "accent": "#0078d4",
    "text_bg": "#ffffff",
    "text_fg": "#1f1f1f",
    "log_info": "#7a7a7a",
    "log_success": "#0e7a0e",
    "log_error": "#c42b1c",
    "log_warning": "#b25f00",
    "status_success": "#0e7a0e",
    "status_error": "#c42b1c",
}

DARK_COLORS = {
    "bg": "#202020",
    "fg": "#e8e8e8",
    "border": "#4a4a4a",
    "field": "#2d2d2d",
    "button_bg": "#383838",
    "button_fg": "#f2f2f2",
    "button_hover": "#454545",
    "button_press": "#2e2e2e",
    "disabled_fg": "#6f6f6f",
    "trough": "#3a3a3a",
    "select_bg": "#4cc2ff",
    "select_fg": "#101010",
    "accent": "#4cc2ff",
    "text_bg": "#1b1b1b",
    "text_fg": "#d8d8d8",
    "log_info": "#9a9a9a",
    "log_success": "#71d371",
    "log_error": "#ff8a8a",
    "log_warning": "#ffc14d",
    "status_success": "#71d371",
    "status_error": "#ff8a8a",
}

if sys.platform == "win32":
    import winreg

_WINDOWS_PERSONALIZE_KEY = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"


def get_system_theme() -> str:
    """读取 Windows 系统「应用模式」设置（设置 - 个性化 - 颜色）

    注册表 AppsUseLightTheme：1 为浅色，0 为深色。
    键不存在（旧版系统）或非 Windows 平台时返回浅色。
    """
    if sys.platform != "win32":
        return THEME_LIGHT
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _WINDOWS_PERSONALIZE_KEY) as key:
            use_light, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return THEME_LIGHT if use_light else THEME_DARK
    except OSError:
        return THEME_LIGHT


def set_titlebar_theme(root, theme: str):
    """让窗口标题栏跟随应用主题（DWMWA_USE_IMMERSIVE_DARK_MODE）

    仅 Windows 10 1809+ 生效，旧系统或调用失败时保持系统默认，静默忽略。
    设置属性后需 SWP_FRAMECHANGED 触发非客户区重绘才会立即生效。
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes

        hwnd = wintypes.HWND(ctypes.windll.user32.GetParent(root.winfo_id()) or int(root.frame(), 16))
        value = ctypes.c_int(1 if theme == THEME_DARK else 0)
        # 属性 20 为新版 DWMWA_USE_IMMERSIVE_DARK_MODE，部分旧版本构建为 19
        applied = False
        for attr in (20, 19):
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, wintypes.DWORD(attr), ctypes.byref(value), ctypes.sizeof(value)
            ) == 0:
                applied = True
                break
        if applied:
            SWP_FRAMECHANGED = 0x20
            SWP_NOSIZE = 0x1
            SWP_NOMOVE = 0x2
            SWP_NOZORDER = 0x4
            SWP_NOACTIVATE = 0x10
            ctypes.windll.user32.SetWindowPos(
                hwnd, 0, 0, 0, 0, 0,
                SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED,
            )
    except Exception:
        pass


def configure_ttk(root, colors: dict):
    """将整套配色应用到 ttk 样式

    统一使用 clam 主题（Windows 原生主题不支持自定义控件颜色），
    保证深浅两套模式下控件形态一致，仅配色不同。
    """
    style = ttk.Style(root)
    style.theme_use("clam")

    root.configure(background=colors["bg"])

    # 下拉框弹出列表是独立创建的 Tk Listbox，只能通过 option_add 配色
    root.option_add("*TCombobox*Listbox.background", colors["field"])
    root.option_add("*TCombobox*Listbox.foreground", colors["fg"])
    root.option_add("*TCombobox*Listbox.selectBackground", colors["select_bg"])
    root.option_add("*TCombobox*Listbox.selectForeground", colors["select_fg"])

    style.configure(
        ".",
        background=colors["bg"],
        foreground=colors["fg"],
        fieldbackground=colors["field"],
        bordercolor=colors["border"],
        lightcolor=colors["bg"],
        darkcolor=colors["bg"],
        troughcolor=colors["trough"],
        focuscolor=colors["accent"],
        selectbackground=colors["select_bg"],
        selectforeground=colors["select_fg"],
        insertcolor=colors["fg"],
    )

    style.configure("TFrame", background=colors["bg"])
    style.configure("TLabel", background=colors["bg"], foreground=colors["fg"])
    style.configure(
        "TLabelframe",
        background=colors["bg"],
        bordercolor=colors["border"],
        lightcolor=colors["bg"],
        darkcolor=colors["bg"],
    )
    style.configure("TLabelframe.Label", background=colors["bg"], foreground=colors["fg"])

    style.configure(
        "TButton",
        background=colors["button_bg"],
        foreground=colors["button_fg"],
        bordercolor=colors["border"],
        lightcolor=colors["button_bg"],
        darkcolor=colors["button_bg"],
        focuscolor=colors["accent"],
        padding=(10, 3),
    )
    style.map(
        "TButton",
        background=[
            ("disabled", colors["bg"]),
            ("pressed", colors["button_press"]),
            ("active", colors["button_hover"]),
        ],
        foreground=[("disabled", colors["disabled_fg"])],
        lightcolor=[("pressed", colors["button_press"])],
        darkcolor=[("pressed", colors["button_press"])],
        bordercolor=[("focus", colors["accent"])],
    )

    style.configure(
        "TCombobox",
        fieldbackground=colors["field"],
        background=colors["button_bg"],
        foreground=colors["fg"],
        arrowcolor=colors["fg"],
        bordercolor=colors["border"],
        lightcolor=colors["border"],
        darkcolor=colors["border"],
        insertcolor=colors["fg"],
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", colors["field"]), ("disabled", colors["bg"])],
        foreground=[("readonly", colors["fg"]), ("disabled", colors["disabled_fg"])],
        selectbackground=[("readonly", colors["field"])],
        selectforeground=[("readonly", colors["fg"])],
        bordercolor=[("focus", colors["accent"])],
        lightcolor=[("focus", colors["accent"])],
        darkcolor=[("focus", colors["accent"])],
    )

    style.configure(
        "TScale",
        background=colors["bg"],
        troughcolor=colors["trough"],
        bordercolor=colors["border"],
        lightcolor=colors["border"],
        darkcolor=colors["border"],
    )
    style.map("TScale", background=[("active", colors["bg"])])

    style.configure(
        "TScrollbar",
        background=colors["button_bg"],
        troughcolor=colors["bg"],
        bordercolor=colors["bg"],
        arrowcolor=colors["fg"],
        lightcolor=colors["button_bg"],
        darkcolor=colors["button_bg"],
    )
    style.map(
        "TScrollbar",
        background=[("active", colors["button_hover"]), ("pressed", colors["button_press"])],
    )

    style.configure(
        "TRadiobutton",
        background=colors["bg"],
        foreground=colors["fg"],
        indicatorcolor=colors["field"],
        bordercolor=colors["border"],
        focuscolor=colors["accent"],
    )
    style.map(
        "TRadiobutton",
        background=[("active", colors["bg"])],
        indicatorcolor=[("selected", colors["accent"]), ("pressed", colors["accent"])],
    )

