"""
Windows 显示器亮度控制模块
通过 DDC/CI 协议控制显示器亮度

依赖：仅 Windows 系统，需要 dxva2.dll
"""

import ctypes
import ctypes.wintypes
import sys
from typing import Optional

# --- Windows API 常量与结构体定义 ---

class PHYSICAL_MONITOR(ctypes.Structure):
    _fields_ = [
        ("hPhysicalMonitor", ctypes.wintypes.HANDLE),
        ("szPhysicalMonitorDescription", ctypes.c_wchar * 128),
    ]


class MonitorController:
    """显示器控制器，管理物理显示器句柄的生命周期"""

    # --- VCP 代码常量 ---
    VCP_CONTRAST = 0x12      # 对比度
    VCP_RED_GAIN = 0x16      # 红色增益
    VCP_GREEN_GAIN = 0x18    # 绿色增益
    VCP_BLUE_GAIN = 0x1A     # 蓝色增益

    def __init__(self):
        self.monitors = []
        self._loaded = False

    def load_dll(self) -> bool:
        """加载 dxva2.dll"""
        if self._loaded:
            return True

        try:
            self.dxva2 = ctypes.windll.dxva2
            self._setup_functions()
            self._loaded = True
            return True
        except OSError as e:
            print(f"错误：无法加载 dxva2.dll。请确保在 Windows 系统上运行。详情：{e}")
            return False

    def _setup_functions(self):
        """设置 Windows API 函数原型"""
        dxva2 = self.dxva2

        # GetNumberOfPhysicalMonitorsFromHMONITOR
        self.GetNumberOfPhysicalMonitorsFromHMONITOR = dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR
        self.GetNumberOfPhysicalMonitorsFromHMONITOR.argtypes = [
            ctypes.wintypes.HMONITOR,
            ctypes.POINTER(ctypes.wintypes.DWORD)
        ]
        self.GetNumberOfPhysicalMonitorsFromHMONITOR.restype = ctypes.wintypes.BOOL

        # GetPhysicalMonitorsFromHMONITOR
        self.GetPhysicalMonitorsFromHMONITOR = dxva2.GetPhysicalMonitorsFromHMONITOR
        self.GetPhysicalMonitorsFromHMONITOR.argtypes = [
            ctypes.wintypes.HMONITOR,
            ctypes.wintypes.DWORD,
            ctypes.POINTER(PHYSICAL_MONITOR)
        ]
        self.GetPhysicalMonitorsFromHMONITOR.restype = ctypes.wintypes.BOOL

        # GetMonitorBrightness
        self.GetMonitorBrightness = dxva2.GetMonitorBrightness
        self.GetMonitorBrightness.argtypes = [
            ctypes.wintypes.HANDLE,
            ctypes.POINTER(ctypes.wintypes.DWORD),
            ctypes.POINTER(ctypes.wintypes.DWORD),
            ctypes.POINTER(ctypes.wintypes.DWORD)
        ]
        self.GetMonitorBrightness.restype = ctypes.wintypes.BOOL

        # SetMonitorBrightness
        self.SetMonitorBrightness = dxva2.SetMonitorBrightness
        self.SetMonitorBrightness.argtypes = [
            ctypes.wintypes.HANDLE,
            ctypes.wintypes.DWORD
        ]
        self.SetMonitorBrightness.restype = ctypes.wintypes.BOOL

        # GetVCPFeatureAndVCPFeatureReply
        self.GetVCPFeatureAndVCPFeatureReply = dxva2.GetVCPFeatureAndVCPFeatureReply
        self.GetVCPFeatureAndVCPFeatureReply.argtypes = [
            ctypes.wintypes.HANDLE,
            ctypes.wintypes.BYTE,
            ctypes.POINTER(ctypes.wintypes.DWORD),
            ctypes.POINTER(ctypes.wintypes.DWORD),
            ctypes.POINTER(ctypes.wintypes.DWORD)
        ]
        self.GetVCPFeatureAndVCPFeatureReply.restype = ctypes.wintypes.BOOL

        # SetVCPFeature
        self.SetVCPFeature = dxva2.SetVCPFeature
        self.SetVCPFeature.argtypes = [
            ctypes.wintypes.HANDLE,
            ctypes.wintypes.BYTE,
            ctypes.wintypes.DWORD
        ]
        self.SetVCPFeature.restype = ctypes.wintypes.BOOL

        # DestroyPhysicalMonitors
        self.DestroyPhysicalMonitors = dxva2.DestroyPhysicalMonitors
        self.DestroyPhysicalMonitors.argtypes = [
            ctypes.wintypes.DWORD,
            ctypes.POINTER(PHYSICAL_MONITOR)
        ]
        self.DestroyPhysicalMonitors.restype = ctypes.wintypes.BOOL

    def get_monitor_handles(self) -> list:
        """获取所有物理显示器的句柄和描述（纯函数，不修改实例状态）"""
        if not self._loaded and not self.load_dll():
            return []

        monitors = []

        def callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
            num_monitors = ctypes.wintypes.DWORD()
            if not self.GetNumberOfPhysicalMonitorsFromHMONITOR(hMonitor, ctypes.byref(num_monitors)):
                return True
            count = num_monitors.value
            if count == 0:
                return True
            local_array = (PHYSICAL_MONITOR * count)()
            if self.GetPhysicalMonitorsFromHMONITOR(hMonitor, count, local_array):
                for i in range(count):
                    monitors.append({
                        "handle": local_array[i].hPhysicalMonitor,
                        "description": local_array[i].szPhysicalMonitorDescription,
                    })
            return True

        MONITORENUMPROC = ctypes.WINFUNCTYPE(
            ctypes.wintypes.BOOL,
            ctypes.wintypes.HMONITOR,
            ctypes.wintypes.HDC,
            ctypes.POINTER(ctypes.wintypes.RECT),
            ctypes.wintypes.LPARAM
        )
        callback_func = MONITORENUMPROC(callback)
        ctypes.windll.user32.EnumDisplayMonitors(None, None, callback_func, 0)
        return monitors

    def set_brightness_for_monitor(self, handle, target_brightness: int) -> tuple:
        """设置指定显示器的亮度"""
        min_bright = ctypes.wintypes.DWORD()
        cur_bright = ctypes.wintypes.DWORD()
        max_bright = ctypes.wintypes.DWORD()

        if not self.GetMonitorBrightness(handle, ctypes.byref(min_bright),
                                          ctypes.byref(cur_bright),
                                          ctypes.byref(max_bright)):
            err = ctypes.get_last_error()
            return False, f"获取亮度信息失败 (Error Code: {err})"

        actual_target = max(min_bright.value, min(max_bright.value, target_brightness))

        if self.SetMonitorBrightness(handle, actual_target):
            return True, f"亮度已设置为 {actual_target} (范围：{min_bright.value}-{max_bright.value})"
        else:
            err = ctypes.get_last_error()
            return False, f"设置亮度失败 (Error Code: {err})"

    def get_current_brightness(self, handle):
        """获取当前亮度"""
        min_bright = ctypes.wintypes.DWORD()
        cur_bright = ctypes.wintypes.DWORD()
        max_bright = ctypes.wintypes.DWORD()

        if self.GetMonitorBrightness(handle, ctypes.byref(min_bright),
                                      ctypes.byref(cur_bright),
                                      ctypes.byref(max_bright)):
            return cur_bright.value, min_bright.value, max_bright.value
        return None, None, None

    def cleanup_monitors(self, monitors: list):
        """销毁物理显示器句柄，防止资源泄漏"""
        if not self._loaded:
            return

        for mon in monitors:
            try:
                single_array = (PHYSICAL_MONITOR * 1)()
                single_array[0].hPhysicalMonitor = mon["handle"]
                single_array[0].szPhysicalMonitorDescription = mon.get("description", "")
                self.DestroyPhysicalMonitors(1, single_array)
            except Exception:
                pass

    def control_monitor_brightness(self, target_brightness_percent: int,
                                   description: Optional[str] = None) -> dict:
        """
        控制显示器亮度

        参数:
            target_brightness_percent (int): 目标亮度百分比 (0-100)
            description (str, optional): 显示器描述关键字，None 表示控制所有显示器

        返回:
            dict: 包含操作结果的字典
        """
        if not 0 <= target_brightness_percent <= 100:
            return {
                "success": False,
                "results": [],
                "message": f"亮度百分比必须在 0-100 之间，当前值：{target_brightness_percent}"
            }

        all_monitors = self.get_monitor_handles()

        if not all_monitors:
            return {
                "success": False,
                "results": [],
                "message": "未检测到任何支持 DDC/CI 的物理显示器"
            }

        if description:
            monitor_list = [m for m in all_monitors if description in m['description']]
            if not monitor_list:
                self.cleanup_monitors(all_monitors)
                return {
                    "success": False,
                    "results": [],
                    "message": f"未找到描述中包含 '{description}' 的显示器"
                }
        else:
            monitor_list = all_monitors

        results = []
        success_count = 0

        try:
            for mon in monitor_list:
                curr, min_val, max_val = self.get_current_brightness(mon["handle"])
                if curr is None:
                    results.append({
                        "description": mon['description'],
                        "success": False,
                        "message": "无法读取亮度 (可能权限不足)"
                    })
                    continue

                target = int((max_val - min_val) * target_brightness_percent / 100) + min_val
                success, msg = self.set_brightness_for_monitor(mon["handle"], target)

                if success:
                    results.append({
                        "description": mon['description'],
                        "success": True,
                        "message": msg
                    })
                    success_count += 1
                else:
                    results.append({
                        "description": mon['description'],
                        "success": False,
                        "message": msg
                    })

            return {
                "success": success_count == len(monitor_list),
                "results": results,
                "message": f"操作完成。成功：{success_count}/{len(monitor_list)} 个显示器"
            }
        finally:
            self.cleanup_monitors(all_monitors)

    # --- VCP 功能 ---

    def get_vcp_feature(self, handle, vcp_code: int):
        """
        获取 VCP 功能当前值、最小值和最大值

        返回:
            tuple: (当前值，最小值，最大值) 或 (None, None, None) 如果失败
        """
        if not self._loaded and not self.load_dll():
            return None, None, None

        current = ctypes.wintypes.DWORD()
        min_val = ctypes.wintypes.DWORD()
        max_val = ctypes.wintypes.DWORD()

        if self.GetVCPFeatureAndVCPFeatureReply(
            handle, vcp_code, ctypes.byref(min_val),
            ctypes.byref(current), ctypes.byref(max_val)
        ):
            return current.value, min_val.value, max_val.value
        return None, None, None

    def set_vcp_feature(self, handle, vcp_code: int, value: int) -> tuple:
        """
        设置 VCP 功能值

        返回:
            tuple: (成功标志，消息)
        """
        if not self._loaded and not self.load_dll():
            return False, "无法加载 dxva2.dll"

        min_val = ctypes.wintypes.DWORD()
        current = ctypes.wintypes.DWORD()
        max_val = ctypes.wintypes.DWORD()

        if not self.GetVCPFeatureAndVCPFeatureReply(
            handle, vcp_code, ctypes.byref(min_val),
            ctypes.byref(current), ctypes.byref(max_val)
        ):
            err = ctypes.get_last_error()
            return False, f"获取 VCP 信息失败 (Error Code: {err})"

        actual_value = max(min_val.value, min(max_val.value, value))

        if self.SetVCPFeature(handle, vcp_code, actual_value):
            return True, f"已设置为 {actual_value} (范围：{min_val.value}-{max_val.value})"
        else:
            err = ctypes.get_last_error()
            return False, f"设置 VCP 失败 (Error Code: {err})"

    def get_vcp_feature_percent(self, handle, vcp_code: int):
        """
        获取 VCP 功能的百分比值

        返回:
            dict: 包含当前值、最小值、最大值和百分比的字典
        """
        curr, min_val, max_val = self.get_vcp_feature(handle, vcp_code)
        if curr is None:
            return None

        percent = round((curr - min_val) / (max_val - min_val) * 100) if max_val != min_val else 0
        return {
            "current": curr,
            "min": min_val,
            "max": max_val,
            "percent": percent
        }

    def control_vcp_feature(self, vcp_code: int, vcp_name: str, target_percent: int,
                            description: Optional[str] = None) -> dict:
        """
        控制显示器 VCP 功能（通用方法）

        参数:
            vcp_code: VCP 代码
            vcp_name: VCP 功能名称（用于返回消息）
            target_percent: 目标百分比 (0-100)
            description: 显示器描述关键字，None 表示控制所有显示器

        返回:
            dict: 包含操作结果的字典
        """
        if not 0 <= target_percent <= 100:
            return {
                "success": False,
                "results": [],
                "message": f"{vcp_name}必须在 0-100 之间，当前值：{target_percent}"
            }

        all_monitors = self.get_monitor_handles()

        if not all_monitors:
            return {
                "success": False,
                "results": [],
                "message": "未检测到任何支持 DDC/CI 的物理显示器"
            }

        if description:
            monitor_list = [m for m in all_monitors if description in m['description']]
            if not monitor_list:
                self.cleanup_monitors(all_monitors)
                return {
                    "success": False,
                    "results": [],
                    "message": f"未找到描述中包含 '{description}' 的显示器"
                }
        else:
            monitor_list = all_monitors

        results = []
        success_count = 0

        try:
            for mon in monitor_list:
                curr, min_val, max_val = self.get_vcp_feature(mon["handle"], vcp_code)
                if curr is None:
                    results.append({
                        "description": mon['description'],
                        "success": False,
                        "message": f"无法读取{vcp_name} (可能不支持该功能)"
                    })
                    continue

                target = int((max_val - min_val) * target_percent / 100) + min_val
                success, msg = self.set_vcp_feature(mon["handle"], vcp_code, target)

                if success:
                    results.append({
                        "description": mon['description'],
                        "success": True,
                        "message": msg
                    })
                    success_count += 1
                else:
                    results.append({
                        "description": mon['description'],
                        "success": False,
                        "message": msg
                    })

            return {
                "success": success_count == len(monitor_list),
                "results": results,
                "message": f"操作完成。成功：{success_count}/{len(monitor_list)} 个显示器"
            }
        finally:
            self.cleanup_monitors(all_monitors)

    # --- 对比度控制 ---

    def set_contrast(self, contrast_percent: int, description: Optional[str] = None) -> dict:
        """设置显示器对比度"""
        return self.control_vcp_feature(self.VCP_CONTRAST, "对比度", contrast_percent, description)

    def get_contrast(self, description: Optional[str] = None) -> dict:
        """获取显示器对比度信息"""
        all_monitors = self.get_monitor_handles()

        if not all_monitors:
            return {
                "success": False,
                "message": "未检测到任何支持 DDC/CI 的物理显示器"
            }

        if description:
            monitor_list = [m for m in all_monitors if description in m['description']]
            if not monitor_list:
                self.cleanup_monitors(all_monitors)
                return {
                    "success": False,
                    "message": f"未找到描述中包含 '{description}' 的显示器"
                }
        else:
            monitor_list = all_monitors

        results = []
        try:
            for mon in monitor_list:
                info = self.get_vcp_feature_percent(mon["handle"], self.VCP_CONTRAST)
                if info:
                    results.append({
                        "description": mon['description'],
                        "success": True,
                        **info
                    })
                else:
                    results.append({
                        "description": mon['description'],
                        "success": False,
                        "message": "无法读取对比度"
                    })

            return {
                "success": all(r.get("success", False) for r in results),
                "monitor_count": len(results),
                "monitors": results
            }
        finally:
            self.cleanup_monitors(all_monitors)

    # --- RGB 增益控制 ---

    _GAIN_COLOR_MAP = {
        "red": (VCP_RED_GAIN, "红色增益"),
        "green": (VCP_GREEN_GAIN, "绿色增益"),
        "blue": (VCP_BLUE_GAIN, "蓝色增益"),
    }

    _GAIN_COLOR_NAME = {
        "red": (VCP_RED_GAIN, "红色"),
        "green": (VCP_GREEN_GAIN, "绿色"),
        "blue": (VCP_BLUE_GAIN, "蓝色"),
    }

    def set_gain(self, color: str, gain_percent: int, description: Optional[str] = None) -> dict:
        """设置显示器 RGB 增益"""
        if color not in self._GAIN_COLOR_MAP:
            return {
                "success": False,
                "message": f"无效的颜色通道：{color}。必须是 'red', 'green' 或 'blue'"
            }

        vcp_code, vcp_name = self._GAIN_COLOR_MAP[color]
        return self.control_vcp_feature(vcp_code, vcp_name, gain_percent, description)

    def get_gain(self, color: str, description: Optional[str] = None) -> dict:
        """获取显示器 RGB 增益信息"""
        if color not in self._GAIN_COLOR_NAME:
            return {
                "success": False,
                "message": f"无效的颜色通道：{color}。必须是 'red', 'green' 或 'blue'"
            }

        vcp_code, vcp_name = self._GAIN_COLOR_NAME[color]
        all_monitors = self.get_monitor_handles()

        if not all_monitors:
            return {
                "success": False,
                "message": "未检测到任何支持 DDC/CI 的物理显示器"
            }

        if description:
            monitor_list = [m for m in all_monitors if description in m['description']]
            if not monitor_list:
                self.cleanup_monitors(all_monitors)
                return {
                    "success": False,
                    "message": f"未找到描述中包含 '{description}' 的显示器"
                }
        else:
            monitor_list = all_monitors

        results = []
        try:
            for mon in monitor_list:
                info = self.get_vcp_feature_percent(mon["handle"], vcp_code)
                if info:
                    results.append({
                        "description": mon['description'],
                        "success": True,
                        **info
                    })
                else:
                    results.append({
                        "description": mon['description'],
                        "success": False,
                        "message": f"无法读取{vcp_name}增益"
                    })

            return {
                "success": all(r.get("success", False) for r in results),
                "monitor_count": len(results),
                "monitors": results
            }
        finally:
            self.cleanup_monitors(all_monitors)

    def get_all_gains(self, description: Optional[str] = None) -> dict:
        """获取显示器所有 RGB 增益信息"""
        all_monitors = self.get_monitor_handles()

        if not all_monitors:
            return {
                "success": False,
                "message": "未检测到任何支持 DDC/CI 的物理显示器"
            }

        if description:
            monitor_list = [m for m in all_monitors if description in m['description']]
            if not monitor_list:
                self.cleanup_monitors(all_monitors)
                return {
                    "success": False,
                    "message": f"未找到描述中包含 '{description}' 的显示器"
                }
        else:
            monitor_list = all_monitors

        results = []
        try:
            for mon in monitor_list:
                red_info = self.get_vcp_feature_percent(mon["handle"], self.VCP_RED_GAIN)
                green_info = self.get_vcp_feature_percent(mon["handle"], self.VCP_GREEN_GAIN)
                blue_info = self.get_vcp_feature_percent(mon["handle"], self.VCP_BLUE_GAIN)

                monitor_result = {
                    "description": mon['description'],
                    "success": True,
                    "gains": {}
                }

                if red_info:
                    monitor_result["gains"]["red"] = red_info
                else:
                    monitor_result["success"] = False
                    monitor_result["error"] = "无法读取红色增益"

                if green_info:
                    monitor_result["gains"]["green"] = green_info
                else:
                    monitor_result["success"] = False
                    monitor_result["error"] = "无法读取绿色增益"

                if blue_info:
                    monitor_result["gains"]["blue"] = blue_info
                else:
                    monitor_result["success"] = False
                    monitor_result["error"] = "无法读取蓝色增益"

                results.append(monitor_result)

            return {
                "success": all(r.get("success", False) for r in results),
                "monitor_count": len(results),
                "monitors": results
            }
        finally:
            self.cleanup_monitors(all_monitors)


if __name__ == "__main__":
    print("=" * 50)
    print("Windows 外接显示器亮度控制工具 (DDC/CI)")
    print("=" * 50)
    print()

    controller = MonitorController()

    if not controller.load_dll():
        sys.exit(1)

    # ========== 使用示例 ==========

    # 示例 1: 将所有显示器亮度设置为 50%
    print("【示例 1】将所有显示器亮度设置为 50%")
    result = controller.control_monitor_brightness(50)
    print(f"结果：{result['message']}")
    if not result['success']:
        for r in result['results']:
            print(f"  - {r['description']}: {r['message']}")
    print()
