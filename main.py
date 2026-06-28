"""
显示器亮度控制 UI 程序
基于 DDC/CI 协议，使用 tkinter 实现图形界面
"""

import json
import os
import tkinter as tk
from tkinter import ttk, scrolledtext, font
from datetime import datetime
from typing import Optional

from monitor_brightness import MonitorController
from brightness_predictor import predict_brightness


HISTORY_LOG_FILE = "history.log"


# 启用 Windows 高 DPI 支持
try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(2)  # Per Monitor DPI v2
except Exception:
    pass


class MonitorBrightnessApp:
    """显示器亮度控制应用程序"""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("显示器亮度控制")
        self.root.resizable(True, True)
        
        # 配置字体渲染
        self._setup_fonts()

        # 初始化控制器
        self.controller = MonitorController()
        self.controller.load_dll()

        # 加载配置文件
        self.config_file = "config.json"
        self.config = self.load_config()

        # 存储显示器信息
        self.monitors = []
        self.selected_monitor_desc: Optional[str] = None

        # 创建界面
        self.create_widgets()

        # 刷新显示器列表
        self.refresh_monitors()

        # 根据历史习惯自动调节亮度
        self.auto_adjust_brightness()

        # 初始日志
        self.log("程序启动", "info")

        # 窗口关闭时清理资源
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        """窗口关闭时清理显示器句柄"""
        if self.monitors:
            self.controller.cleanup_monitors(self.monitors)
            self.monitors = []
        self.root.destroy()

    def _setup_fonts(self):
        """设置字体渲染，优化高 DPI 显示"""
        # 启用字体平滑
        self.root.option_add("*Font.Smooth", "true")
        
        # 设置默认字体为微软雅黑，根据 DPI 自动缩放
        default_font = font.nametofont("TkDefaultFont")
        default_font.configure(family="Microsoft YaHei UI", size=10)
        
        text_font = font.nametofont("TkTextFont")
        text_font.configure(family="Microsoft YaHei UI", size=10)
        
        fixed_font = font.nametofont("TkFixedFont")
        fixed_font.configure(family="Consolas", size=10)

    def load_config(self) -> dict:
        """加载配置文件"""
        default_config = {"brightness": 50, "last_monitor": ""}
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    return {**default_config, **config}
        except (json.JSONDecodeError, IOError) as e:
            print(f"加载配置文件失败：{e}")
        return default_config

    def save_config(self):
        """保存配置文件"""
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except IOError as e:
            self.log(f"保存配置文件失败：{e}", "error")

    def log(self, message: str, level: str = "info"):
        """添加日志到日志窗口"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        level_colors = {
            "info": "gray",
            "success": "green",
            "error": "red",
            "warning": "orange"
        }
        color = level_colors.get(level, "gray")

        log_entry = f"[{timestamp}] {message}\n"
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, log_entry, level)
        self.log_text.tag_config(level, foreground=color)
        self.log_text.config(state=tk.DISABLED)
        self.log_text.see(tk.END)

    def record_history(self, brightness: int, monitor_desc: str):
        """记录亮度操作到历史日志文件"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] 显示器：{monitor_desc} | 亮度设置为：{brightness}%\n"
        try:
            with open(HISTORY_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except IOError as e:
            self.log(f"记录历史日志失败：{e}", "error")

    def clear_log(self):
        """清空日志"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.log("日志已清空", "info")

    def on_brightness_change(self, event=None):
        """滑条值变化时的处理（仅更新显示，不应用）"""
        brightness = self.brightness_var.get()
        self.brightness_value_label.config(text=f"{brightness}%")

    def create_widgets(self):
        """创建界面组件"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置行列权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(4, weight=1)

        # 显示器选择区域
        monitor_frame = ttk.LabelFrame(main_frame, text="选择显示器", padding="10")
        monitor_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        # 刷新按钮
        refresh_btn = ttk.Button(monitor_frame, text="刷新", command=self.refresh_monitors)
        refresh_btn.grid(row=0, column=0, padx=(0, 10))

        # 显示器下拉框
        self.monitor_var = tk.StringVar()
        self.monitor_combo = ttk.Combobox(
            monitor_frame,
            textvariable=self.monitor_var,
            state="readonly",
            width=50
        )
        self.monitor_combo.grid(row=0, column=1, sticky=(tk.W, tk.E))
        self.monitor_combo.bind("<<ComboboxSelected>>", self.on_monitor_selected)

        monitor_frame.columnconfigure(1, weight=1)

        # 当前亮度显示
        info_frame = ttk.LabelFrame(main_frame, text="当前亮度", padding="10")
        info_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        self.brightness_label = ttk.Label(info_frame, text="未选择显示器", font=("Microsoft YaHei UI", 24, "bold"))
        self.brightness_label.grid(row=0, column=0)

        # 亮度设置区域
        setting_frame = ttk.LabelFrame(main_frame, text="设置亮度", padding="10")
        setting_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        setting_frame.columnconfigure(1, weight=1)

        # 滑条
        self.brightness_var = tk.IntVar(value=self.config.get("brightness", 50))
        self.brightness_scale = ttk.Scale(
            setting_frame,
            from_=0,
            to=100,
            variable=self.brightness_var,
            orient=tk.HORIZONTAL,
            command=self.on_brightness_change,
            length=300
        )
        self.brightness_scale.grid(row=0, column=0, padx=(0, 10), sticky=(tk.W, tk.E))

        # 亮度值显示
        self.brightness_value_label = ttk.Label(
            setting_frame,
            text=f"{self.brightness_var.get()}%",
            font=("Microsoft YaHei UI", 14, "bold"),
            width=6
        )
        self.brightness_value_label.grid(row=0, column=1, padx=(0, 10))

        # 保存按钮
        save_btn = ttk.Button(setting_frame, text="保存", command=self.save_brightness)
        save_btn.grid(row=0, column=2, padx=(10, 0))

        # 状态标签
        self.status_label = ttk.Label(main_frame, text="", foreground="green")
        self.status_label.grid(row=3, column=0, columnspan=2, pady=(10, 0))

        # 日志区域
        log_frame = ttk.LabelFrame(main_frame, text="日志", padding="10")
        log_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        # 日志文本框
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=10,
            wrap=tk.WORD,
            font=("Consolas", 11)
        )
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 日志按钮框架
        log_btn_frame = ttk.Frame(log_frame)
        log_btn_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(5, 0))

        clear_log_btn = ttk.Button(log_btn_frame, text="清空日志", command=self.clear_log)
        clear_log_btn.pack(side=tk.LEFT)

    def refresh_monitors(self):
        """刷新显示器列表"""
        # 清理旧句柄，防止资源泄漏
        if self.monitors:
            self.controller.cleanup_monitors(self.monitors)

        self.monitors = self.controller.get_monitor_handles()

        if not self.monitors:
            self.monitor_combo["values"] = ["未检测到支持 DDC/CI 的显示器"]
            self.monitor_var.set("未检测到支持 DDC/CI 的显示器")
            self.selected_monitor_desc = None
            self.brightness_label.config(text="无显示器")
            self.log("未检测到支持 DDC/CI 的显示器", "warning")
            return

        # 更新下拉框
        monitor_descriptions = [m["description"] for m in self.monitors]
        self.monitor_combo["values"] = monitor_descriptions
        self.log(f"检测到 {len(self.monitors)} 个显示器", "info")

        # 恢复上次选择的显示器
        last_monitor = self.config.get("last_monitor", "")
        if last_monitor in monitor_descriptions:
            self.monitor_var.set(last_monitor)
            self.selected_monitor_desc = last_monitor
        else:
            self.monitor_var.set(monitor_descriptions[0])
            self.selected_monitor_desc = monitor_descriptions[0]

        # 查询当前亮度
        self.query_current_brightness()

    def auto_adjust_brightness(self):
        """根据历史使用习惯自动调节亮度（不记录到 history.log）"""
        if not self.selected_monitor_desc:
            return

        brightness, reason = predict_brightness()
        self.log(f"智能调节：{reason}", "info")

        # 同步滑条
        self.brightness_var.set(brightness)
        self.brightness_value_label.config(text=f"{brightness}%")

        # 保存到配置
        self.config["brightness"] = brightness
        self.save_config()

        # 应用亮度（复用已有句柄，避免重复获取导致句柄失效）
        result = self.controller.control_monitor_brightness(
            brightness, self.selected_monitor_desc, monitors=self.monitors
        )
        if result["success"]:
            self.status_label.config(text=f"智能调节亮度为 {brightness}%", foreground="green")
            self.log(f"自动设置亮度：{brightness}%", "success")
            self.query_current_brightness()
        else:
            self.status_label.config(text="智能调节失败", foreground="red")
            self.log("自动亮度设置失败", "error")
            for r in result.get("results", []):
                status = "success" if r.get("success") else "error"
                self.log(f"  - {r['description']}: {r['message']}", status)

    def on_monitor_selected(self, event):
        """显示器选择变化时的处理"""
        self.selected_monitor_desc = self.monitor_var.get()
        self.config["last_monitor"] = self.selected_monitor_desc
        self.save_config()
        self.log(f"选择显示器：{self.selected_monitor_desc}", "info")
        self.query_current_brightness()

    def get_selected_monitor_handle(self):
        """获取选中显示器的句柄"""
        if not self.selected_monitor_desc:
            return None
        for monitor in self.monitors:
            if monitor["description"] == self.selected_monitor_desc:
                return monitor["handle"]
        return None

    def query_current_brightness(self):
        """查询当前亮度"""
        handle = self.get_selected_monitor_handle()
        if handle is None:
            self.brightness_label.config(text="未选择显示器")
            return

        cur, min_val, max_val = self.controller.get_current_brightness(handle)
        if cur is not None:
            # 计算百分比
            if max_val != min_val:
                percent = round((cur - min_val) / (max_val - min_val) * 100)
            else:
                percent = 0
            self.brightness_label.config(text=f"{percent}%")
            self.status_label.config(text=f"范围：{min_val}-{max_val}")
            self.log(f"当前亮度：{percent}% (范围：{min_val}-{max_val})", "info")
        else:
            self.brightness_label.config(text="读取失败")
            self.status_label.config(text="无法读取亮度信息")
            self.log("无法读取亮度信息", "error")

    def save_brightness(self):
        """保存并应用亮度设置"""
        handle = self.get_selected_monitor_handle()
        if handle is None:
            self.log("请先选择显示器", "warning")
            return

        brightness = self.brightness_var.get()

        # 保存配置
        self.config["brightness"] = brightness
        self.save_config()

        # 应用亮度
        self.log(f"开始设置亮度：{brightness}%", "info")
        result = self.controller.control_monitor_brightness(brightness, self.selected_monitor_desc)

        if result["success"]:
            self.status_label.config(text=f"亮度已设置为 {brightness}%", foreground="green")
            self.query_current_brightness()
            self.log(f"亮度设置成功：{brightness}%", "success")
            for r in result.get("results", []):
                status = "success" if r.get("success") else "error"
                self.log(f"  - {r['description']}: {r['message']}", status)
            # 记录历史
            self.record_history(brightness, self.selected_monitor_desc)
        else:
            self.status_label.config(text="设置失败", foreground="red")
            self.log("亮度设置失败", "error")
            for r in result.get("results", []):
                status = "success" if r.get("success") else "error"
                self.log(f"  - {r['description']}: {r['message']}", status)


def main():
    """主函数"""
    root = tk.Tk()
    app = MonitorBrightnessApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
