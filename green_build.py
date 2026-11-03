import sys
import os
import shutil
import subprocess
import threading
import re
import tkinter as tk
from tkinter import filedialog, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import time
import json
import base64
import traceback
import hashlib
import zipfile

APP_VERSION = "1.2.7"

class GreenBuildApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"GreenBuild - 安卓编译与签名工具 v{APP_VERSION}")
        
        self.root.geometry("1150x850")
        self.root.minsize(1100, 800) 
        self.center_window(1150, 850)
        
        if getattr(sys, 'frozen', False):
            self.BASE_DIR = os.path.dirname(sys.executable)
        else:
            self.BASE_DIR = os.path.dirname(os.path.abspath(__file__))

        icon_path = os.path.join(self.BASE_DIR, "icon.ico")
        if os.path.exists(icon_path):
            self.root.iconbitmap(icon_path)

        self.JDK_HOME = os.path.join(self.BASE_DIR, "jdk")
        self.SDK_HOME = os.path.join(self.BASE_DIR, "sdk")
        self.SDK_MANAGER = os.path.join(self.SDK_HOME, "cmdline-tools", "latest", "bin", "sdkmanager.bat")
        
        self.GRADLE_CACHE_DIR = os.path.join(self.BASE_DIR, "gradle_cache")
        self.TEMP_DIR = os.path.join(self.BASE_DIR, "temp_cache")
        self.ANDROID_USER_DIR = os.path.join(self.BASE_DIR, "android_user_cache")
        self.OFFLINE_DIR = os.path.join(self.BASE_DIR, "offline_packages")
        
        self.CONFIG_FILE = os.path.join(self.BASE_DIR, "sign_configs.json")
        self.JADX_PATH = os.path.join(self.BASE_DIR, "tools", "jadx", "bin", "jadx.bat")
        
        self.DESKTOP_DIR = os.path.join(os.path.expanduser("~"), "Desktop")
        if not os.path.exists(self.DESKTOP_DIR):
            self.DESKTOP_DIR = os.path.join(os.path.expanduser("~"), "桌面")

        self.is_busy = False 
        self.current_downloading_component = None 
        self.active_processes = []
        
        self.init_directories()
        self.setup_ui()
        
        self.root.after(500, self.process_offline_packages)
        
        self.clean_cache()
        self.check_environment()
        self.load_all_sign_configs()
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def center_window(self, width, height):
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = int((screen_width / 2) - (width / 2))
        y = int((screen_height / 2) - (height / 2))
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def init_directories(self):
        dirs = [
            os.path.join(self.SDK_HOME, "platforms"),
            os.path.join(self.SDK_HOME, "build-tools"),
            os.path.join(self.SDK_HOME, "platform-tools"),
            os.path.join(self.SDK_HOME, "cmdline-tools"),
            os.path.join(self.BASE_DIR, "tools"),
            self.GRADLE_CACHE_DIR,
            self.TEMP_DIR,
            self.ANDROID_USER_DIR,
            self.OFFLINE_DIR
        ]
        for d in dirs:
            os.makedirs(d, exist_ok=True)

    def process_offline_packages(self):
        if not os.path.exists(self.OFFLINE_DIR): return
        zips = [f for f in os.listdir(self.OFFLINE_DIR) if f.endswith(".zip")]
        if not zips: return
        self.log(f"\n📦 发现 {len(zips)} 个离线包，正在自动处理...")
        for z in zips:
            zip_path = os.path.join(self.OFFLINE_DIR, z)
            if not os.path.exists(zip_path): continue
            try:
                if "platform-" in z or "android-" in z:
                    self._install_offline_platform(zip_path, z)
                elif "build-tools" in z:
                    self._install_offline_build_tools(zip_path, z)
                elif "gradle" in z:
                    self._install_offline_gradle(zip_path, z)
                else:
                    self.log(f"   ⚠️ 未知的包类型: {z}，请手动处理。")
            except Exception as e:
                self.log(f"   ❌ 处理失败 {z}: {str(e)}")

    def _install_offline_platform(self, zip_path, filename):
        match = re.search(r'android-(\d+)|platform-(\d+)', filename)
        if not match: return
        ver = match.group(1) if match.group(1) else match.group(2)
        
        target_dir = os.path.join(self.SDK_HOME, "platforms", f"android-{ver}")
        temp_extract = os.path.join(self.OFFLINE_DIR, "temp_extract")
        
        self.log(f"   ▸ 正在安装 Android 平台包 (API {ver})...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_extract)
            
        extracted_folder = None
        for root, dirs, files in os.walk(temp_extract):
            if "android.jar" in files:
                extracted_folder = root
                break
                
        if extracted_folder:
            if os.path.exists(target_dir): shutil.rmtree(target_dir)
            shutil.move(extracted_folder, target_dir)
            self.log(f"   ✅ 成功安装到 sdk/platforms/android-{ver}")
        else:
            self.log("   ❌ 压缩包内未找到 android.jar，可能不是有效的平台包。")
            
        shutil.rmtree(temp_extract, ignore_errors=True)
        os.remove(zip_path)
        self.update_sdk_status_ui()

    def _install_offline_build_tools(self, zip_path, filename):
        match = re.search(r'r(\d+)', filename)
        if not match: return
        ver = match.group(1)
        if len(ver) <= 2: ver = f"{ver}.0.0"

        target_dir = os.path.join(self.SDK_HOME, "build-tools", ver)
        temp_extract = os.path.join(self.OFFLINE_DIR, "temp_extract")
        
        self.log(f"   ▸ 正在安装 Build-Tools ({ver})...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_extract)
            
        extracted_folder = None
        for root, dirs, files in os.walk(temp_extract):
            if "aapt.exe" in files or "apksigner.bat" in files:
                extracted_folder = root
                break
                
        if extracted_folder:
            if os.path.exists(target_dir): shutil.rmtree(target_dir)
            shutil.move(extracted_folder, target_dir)
            self.log(f"   ✅ 成功安装到 sdk/build-tools/{ver}")
        else:
            self.log("   ❌ 压缩包内未找到核心工具，可能不是有效的构建工具包。")
            
        shutil.rmtree(temp_extract, ignore_errors=True)
        os.remove(zip_path)

    def _install_offline_gradle(self, zip_path, filename):
        target_path = os.path.join(self.GRADLE_CACHE_DIR, filename)
        if os.path.exists(target_path):
            os.remove(zip_path)
            self.log(f"   ▸ 发现 Gradle 离线包: {filename}，缓存已存在，清理重复文件。")
            return
        try:
            shutil.move(zip_path, target_path)
            self.log(f"   ✅ Gradle 离线包已转移至缓存目录: {filename}")
        except Exception as e:
            self.log(f"   ❌ 移动 Gradle 离线包失败: {e}")

    def get_file_sha1(self, filepath):
        if not os.path.exists(filepath): return None
        hash_sha1 = hashlib.sha1()
        try:
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
                    hash_sha1.update(chunk)
            return hash_sha1.hexdigest()
        except Exception: return None

    def validate_platform_detail(self, folder_path):
        jar_path = os.path.join(folder_path, "android.jar")
        prop_path = os.path.join(folder_path, "source.properties")
        checksum_path = os.path.join(folder_path, "checksum.json")

        if not os.path.exists(prop_path): return False, "缺少 source.properties"
        if not os.path.exists(jar_path): return False, "缺少核心 android.jar"
        
        jar_size = os.path.getsize(jar_path)
        if jar_size < 5 * 1024 * 1024: return False, f"文件过小({jar_size/1024/1024:.1f}MB)"

        jar_mtime = os.path.getmtime(jar_path)
        if os.path.exists(checksum_path):
            try:
                with open(checksum_path, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)
                if cache_data.get("size") == jar_size and cache_data.get("mtime") == jar_mtime:
                    return True, "指纹缓存秒过"
            except: pass

        current_sha1 = self.get_file_sha1(jar_path)
        try:
            cache_data = {"size": jar_size, "mtime": jar_mtime, "sha1": current_sha1}
            with open(checksum_path, "w", encoding="utf-8") as f:
                json.dump(cache_data, f)
            return True, "SHA-1 校验成功"
        except: return False, "无法写入指纹缓存"

    def is_valid_platform(self, folder_path):
        valid, _ = self.validate_platform_detail(folder_path)
        return valid

    def clean_cache(self):
        cleaned = False
        temp_dirs = [os.path.join(self.SDK_HOME, ".temp"), os.path.join(self.SDK_HOME, "temp")]
        for d in temp_dirs:
            if os.path.exists(d):
                try:
                    shutil.rmtree(d)
                    cleaned = True
                except Exception: pass
                    
        platforms_dir = os.path.join(self.SDK_HOME, "platforms")
        if os.path.exists(platforms_dir):
            for item in os.listdir(platforms_dir):
                item_path = os.path.join(platforms_dir, item)
                if os.path.isdir(item_path) and not self.is_valid_platform(item_path):
                    try:
                        shutil.rmtree(item_path)
                        cleaned = True
                    except Exception: pass
                        
        if cleaned: self.log("🧹 启动清理：已自动清理损坏的残缺组件。")

    def kill_all_processes(self):
        """【终极核武】清理该软件目录下衍生的所有进程"""
        if self.active_processes:
            for p in self.active_processes:
                try:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True)
                except: pass
            self.active_processes.clear()

        self.log("🧹 正在深度清理后台残留进程，请稍候...")
        
        # 让子弹飞一会，给系统释放句柄的时间
        time.sleep(0.5)

        # 获取当前运行的软件本身（防止把自己杀了）
        current_pid = os.getpid()

        # 将反斜杠转义，用于 WMI 模糊查询
        safe_path = self.BASE_DIR.replace("\\", "\\\\")

        # 【核心】地毯式查杀：
        # 只要进程的可执行路径包含本软件目录，或者命令行参数里带有本软件目录，并且不是当前主进程，统统杀掉。
        wmic_cmd = (
            f'wmic process where "ProcessId != {current_pid} and '
            f'(ExecutablePath like \'%{safe_path}%\' or CommandLine like \'%{safe_path}%\')" '
            f'call terminate'
        )

        try:
            subprocess.run(wmic_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True)
        except:
            pass

    def cleanup_interrupted_download(self):
        if self.current_downloading_component:
            parts = self.current_downloading_component.split(';')
            if len(parts) == 2:
                pkg_type, pkg_name = parts
                if pkg_type == "platforms":
                    target_dir = os.path.join(self.SDK_HOME, "platforms", pkg_name)
                    if os.path.exists(target_dir) and not self.is_valid_platform(target_dir):
                        try: shutil.rmtree(target_dir)
                        except Exception: pass
            
            temp_dirs = [os.path.join(self.SDK_HOME, ".temp"), os.path.join(self.SDK_HOME, "temp")]
            for d in temp_dirs:
                if os.path.exists(d):
                    try: shutil.rmtree(d)
                    except Exception: pass

    def on_closing(self):
        if self.is_busy:
            if messagebox.askyesno("警告", "当前正在下载或编译中！\n\n强制退出会导致文件损坏，程序将自动杀掉后台进程并清理残留文件。\n你确定要强行关闭吗？"):
                self.kill_all_processes()
                self.cleanup_interrupted_download()
                self.root.destroy()
        else:
            self.kill_all_processes()
            self.root.destroy()

    def setup_ui(self):
        pad_y = 8
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=15, pady=10)
        
        left_container = ttk.Frame(main_frame)
        left_container.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        right_container = ttk.Frame(main_frame, width=380)
        right_container.pack(side="right", fill="y")
        right_container.pack_propagate(False) 

        # ================= 左侧：1. 编译工程 =================
        frame1 = ttk.Labelframe(left_container, text=" 1. 编译工程 ", padding=12, bootstyle="info")
        frame1.pack(fill="x", pady=(0, 10))

        ttk.Label(frame1, text="工程文件夹:").grid(row=0, column=0, sticky="w", pady=pad_y)
        self.project_path_var = ttk.StringVar()
        ttk.Entry(frame1, textvariable=self.project_path_var).grid(row=0, column=1, padx=10, pady=pad_y, sticky="we")
        ttk.Button(frame1, text="浏览...", command=self.browse_project, bootstyle="outline-secondary", width=8).grid(row=0, column=2, pady=pad_y)

        ttk.Label(frame1, text="APK 输出到:").grid(row=1, column=0, sticky="w", pady=pad_y)
        self.output_path_var = ttk.StringVar(value=self.DESKTOP_DIR)
        ttk.Entry(frame1, textvariable=self.output_path_var).grid(row=1, column=1, padx=10, pady=pad_y, sticky="we")
        ttk.Button(frame1, text="浏览...", command=self.browse_output, bootstyle="outline-secondary", width=8).grid(row=1, column=2, pady=pad_y)
        frame1.columnconfigure(1, weight=1)

        # ================= 左侧：2. APK 签名设置 =================
        frame_sign = ttk.Labelframe(left_container, text=" 2. APK 签名配置 (可保存多套) ", padding=12, bootstyle="warning")
        frame_sign.pack(fill="both", expand=True, pady=(0, 10))

        self.enable_sign_var = ttk.BooleanVar(value=False)
        chk_sign = ttk.Checkbutton(frame_sign, text="启用自定义 Release 签名 (不勾选则生成 Debug 包)", 
                                   variable=self.enable_sign_var, bootstyle="round-toggle")
        chk_sign.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 15))

        ttk.Label(frame_sign, text="配置管理:").grid(row=1, column=0, sticky="w", pady=pad_y)
        
        config_row = ttk.Frame(frame_sign)
        config_row.grid(row=1, column=1, sticky="we", padx=(10, 0), pady=pad_y)
        
        ttk.Button(config_row, text="删除", command=self.delete_sign_config, bootstyle="danger-outline", width=8).pack(side="right", padx=(5, 0))
        ttk.Button(config_row, text="保存", command=self.save_sign_config, bootstyle="warning-outline", width=8).pack(side="right", padx=(0, 5))
        
        self.config_name_var = ttk.StringVar(value="默认配置")
        ttk.Entry(config_row, textvariable=self.config_name_var).pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        self.saved_configs_combo = ttk.Combobox(config_row, state="readonly")
        self.saved_configs_combo.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.saved_configs_combo.bind("<<ComboboxSelected>>", self.on_config_selected)

        ttk.Label(frame_sign, text="密钥文件 (.jks):").grid(row=2, column=0, sticky="w", pady=pad_y)
        
        ks_row = ttk.Frame(frame_sign)
        ks_row.grid(row=2, column=1, sticky="we", padx=(10, 0), pady=pad_y)
        
        ttk.Button(ks_row, text="选择...", command=self.browse_keystore, bootstyle="outline-warning", width=8).pack(side="right")
        self.ks_path_var = ttk.StringVar()
        ttk.Entry(ks_row, textvariable=self.ks_path_var).pack(side="left", fill="x", expand=True, padx=(0, 5))

        ttk.Label(frame_sign, text="Store 密码:").grid(row=3, column=0, sticky="w", pady=pad_y)
        self.ks_pass_var = ttk.StringVar()
        ttk.Entry(frame_sign, textvariable=self.ks_pass_var, show="*").grid(row=3, column=1, sticky="we", padx=(10, 0), pady=pad_y)

        ttk.Label(frame_sign, text="Alias 别名:").grid(row=4, column=0, sticky="w", pady=pad_y)
        self.alias_var = ttk.StringVar()
        ttk.Entry(frame_sign, textvariable=self.alias_var).grid(row=4, column=1, sticky="we", padx=(10, 0), pady=pad_y)

        ttk.Label(frame_sign, text="Key 密码:").grid(row=5, column=0, sticky="w", pady=pad_y)
        self.key_pass_var = ttk.StringVar()
        ttk.Entry(frame_sign, textvariable=self.key_pass_var, show="*").grid(row=5, column=1, sticky="we", padx=(10, 0), pady=pad_y)
        
        frame_sign.columnconfigure(1, weight=1)

        # ================= 右侧：3. SDK 组件 =================
        frame_sdk = ttk.Labelframe(right_container, text=" 3. SDK 组件与离线包 ", padding=12, bootstyle="info")
        frame_sdk.pack(fill="x", pady=(0, 10))
        
        ttk.Label(frame_sdk, text="选择缺失组件:").pack(anchor="w", pady=(0, 5))
        self.sdk_combo = ttk.Combobox(frame_sdk, values=[
            "platforms;android-35", "platforms;android-34", "platforms;android-33",
            "platforms;android-32", "platforms;android-31", "platforms;android-30",
            "platforms;android-29",
            "build-tools;35.0.0", "build-tools;34.0.0", "build-tools;33.0.1",
            "build-tools;31.0.0", "build-tools;30.0.3", "build-tools;29.0.3"
        ])
        self.sdk_combo.set("platforms;android-34")
        self.sdk_combo.pack(fill="x", pady=(0, 10))
        
        btn_frame = ttk.Frame(frame_sdk)
        btn_frame.pack(fill="x", pady=(0, 5))
        ttk.Button(btn_frame, text="安装/更新", command=self.start_install_sdk, bootstyle="primary").pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.check_btn = ttk.Button(btn_frame, text="全量检测", command=self.start_full_check, bootstyle="secondary-outline")
        self.check_btn.pack(side="right", fill="x", expand=True, padx=(5, 0))

        # ================= 右侧：4. 工具与生成 =================
        frame_tools = ttk.Labelframe(right_container, text=" 4. 工具与生成 ", padding=12, bootstyle="secondary")
        frame_tools.pack(fill="x", pady=(0, 10))
        
        ttk.Button(frame_tools, text="深度分析项目", command=self.analyze_project, bootstyle="secondary").pack(fill="x", pady=(0, 10), ipady=10)
        
        self.build_btn = ttk.Button(frame_tools, text="全量编译并输出 APK", command=self.start_build, bootstyle="success")
        self.build_btn.pack(fill="x", pady=(0, 15), ipady=10) 
        
        ttk.Separator(frame_tools, orient='horizontal').pack(fill='x', pady=10)
        ttk.Label(frame_tools, text="APK 反编译 (找回源码):").pack(anchor="w", pady=(0, 5))
        
        self.decompile_path_var = ttk.StringVar()
        dec_frame = ttk.Frame(frame_tools)
        dec_frame.pack(fill="x", pady=(0, 10))
        ttk.Entry(dec_frame, textvariable=self.decompile_path_var).pack(side="left", fill="x", expand=True, padx=(0, 5))
        ttk.Button(dec_frame, text="选APK", command=self.browse_apk_to_decompile, bootstyle="outline-secondary", width=8).pack(side="right")
        
        ttk.Button(frame_tools, text="开始反编译", command=self.start_decompile, bootstyle="dark").pack(fill="x", ipady=10)

        # ================= 底部：日志 =================
        bottom_frame = ttk.Frame(self.root)
        bottom_frame.pack(fill="both", expand=True, padx=15, pady=(5, 15))

        frame_log = ttk.Labelframe(bottom_frame, text=" 实时运行日志 ", padding=5)
        frame_log.pack(fill="both", expand=True)
        
        self.console = tk.Text(frame_log, bg="#F8F9FA", fg="#333333", font=("Consolas", 10), insertbackground="black", relief="flat")
        self.console.pack(fill="both", expand=True)
        
        self.log(f"程序版本: v{APP_VERSION}")
        self.log(f"程序运行目录: {self.BASE_DIR}")
        self.log(f"临时缓存目录: {self.TEMP_DIR} (已隔离)")
        self.log(f"📦 离线包放置目录: {self.OFFLINE_DIR}")
        self.log("💡 提示: 将下载的离线包(.zip)放入上述目录，重启软件将自动解压安装。")
        self.log(f"默认输出目录: {self.DESKTOP_DIR}")

    def get_green_env(self):
        env = os.environ.copy()
        env["JAVA_HOME"] = self.JDK_HOME
        env["ANDROID_HOME"] = self.SDK_HOME
        env["ANDROID_SDK_ROOT"] = self.SDK_HOME
        env["GRADLE_USER_HOME"] = self.GRADLE_CACHE_DIR
        env["ANDROID_USER_HOME"] = self.ANDROID_USER_DIR
        env["TEMP"] = self.TEMP_DIR
        env["TMP"] = self.TEMP_DIR
        path_prefix = f"{os.path.join(self.JDK_HOME, 'bin')};{os.path.join(self.SDK_HOME, 'platform-tools')};"
        env["PATH"] = path_prefix + env.get("PATH", "")
        return env

    def prepare_local_gradle(self, project_path):
        wrapper_dir = os.path.join(project_path, "gradle", "wrapper")
        prop_file = os.path.join(wrapper_dir, "gradle-wrapper.properties")
        
        if not os.path.exists(prop_file): return

        try:
            with open(prop_file, "r", encoding="utf-8") as f:
                content = f.read()
            
            match = re.search(r'gradle-([\d.]+)-(?:bin|all)\.zip', content)
            if match:
                version = match.group(1)
                zip_name_bin = f"gradle-{version}-bin.zip"
                
                possible_paths = [
                    os.path.join(self.OFFLINE_DIR, zip_name_bin),
                    os.path.join(self.GRADLE_CACHE_DIR, zip_name_bin)
                ]
                
                target_zip = None
                for p in possible_paths:
                    if os.path.exists(p):
                        target_zip = p
                        break
                        
                if target_zip:
                    abs_path = os.path.abspath(target_zip).replace("\\", "/")
                    file_url = f"file:///{abs_path}"
                    
                    if file_url not in content:
                        new_content = re.sub(r'distributionUrl\s*=.*', f'distributionUrl={file_url}', content)
                        with open(prop_file, "w", encoding="utf-8") as f:
                            f.write(new_content)
                        self.log(f"💡 发现本地 Gradle 离线包！已自动修改工程指向。")
                    return
        except Exception as e:
            self.log(f"⚠️ 自动配置 Gradle 失败: {str(e)}")

    def start_full_check(self):
        if self.is_busy:
            messagebox.showwarning("提示", "当前正在执行任务，请稍后再试！")
            return
        
        self.is_busy = True
        self.check_btn.config(state="disabled", text="检测中...")
        self.log("\n========== 🔍 开始全量深度检测本地组件 ==========")
        threading.Thread(target=self._do_full_scan, daemon=True).start()

    def _do_full_scan(self):
        try:
            platforms_dir = os.path.join(self.SDK_HOME, "platforms")
            build_tools_dir = os.path.join(self.SDK_HOME, "build-tools")
            
            self.log("\n📁 [Platforms 平台包全量检测]:")
            valid_platforms = 0
            if os.path.exists(platforms_dir):
                items = os.listdir(platforms_dir)
                if not items: self.log("   └─ 未安装任何平台包。")
                for item in items:
                    item_path = os.path.join(platforms_dir, item)
                    if os.path.isdir(item_path):
                        is_ok, msg = self._scan_directory_full(item_path)
                        if is_ok: valid_platforms += 1
                        else: self.log(f"   ❌ {item} 异常: {msg}")
            else:
                self.log("   └─ 找不到 platforms 目录。")
                
            self.log("\n📁 [Build-Tools 构建工具全量检测]:")
            valid_tools = 0
            if os.path.exists(build_tools_dir):
                items = os.listdir(build_tools_dir)
                for item in items:
                    item_path = os.path.join(build_tools_dir, item)
                    if os.path.isdir(item_path):
                        is_ok, msg = self._scan_directory_full(item_path)
                        if is_ok: valid_tools += 1
                        else: self.log(f"   ❌ {item} 异常: {msg}")

            self.update_sdk_status_ui()
            self.log(f"\n========== 检测完毕: {valid_platforms} 个有效平台, {valid_tools} 个构建工具 ==========")
        finally:
            self.is_busy = False
            self.root.after(0, lambda: self.check_btn.config(state="normal", text="全量检测"))

    def _scan_directory_full(self, dir_path):
        total_files = 0
        for root, dirs, files in os.walk(dir_path):
            for file in files:
                filepath = os.path.join(root, file)
                try:
                    size = os.path.getsize(filepath)
                    if size == 0: return False, f"0 字节文件 -> {file}"
                    total_files += 1
                except Exception: return False, f"无法读取 -> {file}"
        if total_files < 50: return False, f"文件过少（仅 {total_files} 个），可能没下载完整"
        return True, "正常"

    def _encode_pwd(self, pwd):
        return base64.b64encode(pwd.encode('utf-8')).decode('utf-8') if pwd else ""

    def _decode_pwd(self, enc_str):
        return base64.b64decode(enc_str.encode('utf-8')).decode('utf-8') if enc_str else ""

    def _read_config_file(self):
        if not os.path.exists(self.CONFIG_FILE): return {}
        try:
            with open(self.CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return {}

    def load_all_sign_configs(self):
        configs = self._read_config_file()
        keys = list(configs.keys())
        self.saved_configs_combo['values'] = keys
        if keys: self.log(f"🔧 已加载 {len(keys)} 个本地签名配置。")

    def on_config_selected(self, event):
        selected = self.saved_configs_combo.get()
        if not selected: return
        configs = self._read_config_file()
        if selected in configs:
            cfg = configs[selected]
            self.config_name_var.set(selected)
            self.ks_path_var.set(cfg.get("keystore_path", ""))
            self.ks_pass_var.set(self._decode_pwd(cfg.get("store_pass_enc", "")))
            self.alias_var.set(cfg.get("alias", ""))
            self.key_pass_var.set(self._decode_pwd(cfg.get("key_pass_enc", "")))
            self.enable_sign_var.set(cfg.get("enable_sign", True))
            self.log(f"🔧 已切换并填充配置: {selected}")

    def save_sign_config(self):
        name = self.config_name_var.get().strip()
        if not name:
            messagebox.showwarning("提示", "请先在'配置管理'的左侧输入一个配置名称")
            return
        configs = self._read_config_file()
        configs[name] = {
            "keystore_path": self.ks_path_var.get(),
            "store_pass_enc": self._encode_pwd(self.ks_pass_var.get()),
            "alias": self.alias_var.get(),
            "key_pass_enc": self._encode_pwd(self.key_pass_var.get()),
            "enable_sign": self.enable_sign_var.get()
        }
        try:
            with open(self.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(configs, f, ensure_ascii=False, indent=4)
            self.log(f"💾 配置 [{name}] 已保存！")
            self.load_all_sign_configs()
            self.saved_configs_combo.set(name)
            messagebox.showinfo("成功", f"配置 [{name}] 保存成功！")
        except Exception as e:
            self.log(f"❌ 保存配置失败: {str(e)}")

    def delete_sign_config(self):
        name = self.config_name_var.get().strip()
        if not name: return
        configs = self._read_config_file()
        if name in configs:
            if messagebox.askyesno("确认", f"确定要删除配置 [{name}] 吗？"):
                del configs[name]
                with open(self.CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(configs, f, ensure_ascii=False, indent=4)
                self.log(f"🗑️ 配置 [{name}] 已删除。")
                self.config_name_var.set("")
                self.saved_configs_combo.set("")
                self.ks_path_var.set("")
                self.ks_pass_var.set("")
                self.alias_var.set("")
                self.key_pass_var.set("")
                self.load_all_sign_configs()
        else:
            messagebox.showinfo("提示", "当前配置名称不存在。")

    def log(self, message):
        self.console.insert(tk.END, message + "\n")
        self.console.see(tk.END)

    def check_environment(self):
        self.log("========== 开始环境自检 ==========")
        java_exe = os.path.join(self.JDK_HOME, "bin", "java.exe")
        if not os.path.exists(java_exe):
            self.log("❌ 缺失 JDK！请放入本目录。")
        if not os.path.exists(self.SDK_MANAGER):
            self.log("❌ 缺失 cmdline-tools！请放入 sdk/cmdline-tools/latest/ 目录下。")
        
        self.update_sdk_status_ui()

    def update_sdk_status_ui(self):
        platforms_dir = os.path.join(self.SDK_HOME, "platforms")
        installed = []
        if os.path.exists(platforms_dir):
            for item in os.listdir(platforms_dir):
                item_path = os.path.join(platforms_dir, item)
                if os.path.isdir(item_path) and self.is_valid_platform(item_path):
                    installed.append(item)
                    
        status_text = "📊 [本地已装平台] "
        if installed:
            for item in installed: status_text += f"{item}  "
        else: status_text += "无"
        self.log(status_text)

    def browse_project(self):
        path = filedialog.askdirectory(title="选择Android工程目录")
        if path: self.project_path_var.set(path)

    def browse_output(self):
        path = filedialog.askdirectory(title="选择APK输出目录")
        if path: self.output_path_var.set(path)

    def browse_keystore(self):
        path = filedialog.askopenfilename(title="选择签名文件", filetypes=[("Keystore Files", "*.jks *.keystore"), ("All Files", "*.*")])
        if path: self.ks_path_var.set(path)

    def browse_apk_to_decompile(self):
        path = filedialog.askopenfilename(title="选择要反编译的APK", filetypes=[("APK Files", "*.apk"), ("All Files", "*.*")])
        if path: self.decompile_path_var.set(path)

    def analyze_project(self):
        path = self.project_path_var.get()
        if not path or not os.path.exists(path):
            self.log("❌ 错误：请先选择有效的工程路径！")
            return
        self.log(f"\n🔍 正在深度解析工程: {path} ...")
        has_gradle = os.path.exists(os.path.join(path, "gradlew.bat")) or os.path.exists(os.path.join(path, "gradlew"))
        has_build_gradle = os.path.exists(os.path.join(path, "build.gradle")) or os.path.exists(os.path.join(path, "build.gradle.kts"))
        if not (has_gradle and has_build_gradle):
            self.log("❌ 分析失败：未检测到 gradlew 或根目录的 build.gradle。")
            return
        self.log("✅ [环境] 检测到标准的 Gradle Wrapper 结构。")
        app_gradle = os.path.join(path, "app", "build.gradle")
        if not os.path.exists(app_gradle):
            app_gradle = os.path.join(path, "app", "build.gradle.kts")
        API_MAP = {
            "35": "Android 15", "34": "Android 14", "33": "Android 13", 
            "32": "Android 12L", "31": "Android 12", "30": "Android 11", 
            "29": "Android 10", "28": "Android 9", "27": "Android 8.1", 
            "26": "Android 8.0", "25": "Android 7.1", "24": "Android 7.0"
        }
        if os.path.exists(app_gradle):
            self.log("📄 [配置] 正在读取 app 模块的 Gradle 配置...")
            try:
                with open(app_gradle, "r", encoding="utf-8") as f:
                    content = f.read()
                    sdk_match = re.search(r'compileSdk(?:Version)?\s*[=\s]\s*(\d+)', content)
                    if sdk_match:
                        sdk_ver = sdk_match.group(1)
                        self.log(f"   ▸ 编译 SDK: API {sdk_ver} ({API_MAP.get(sdk_ver, '未知')})")
                        local_platforms = os.path.join(self.SDK_HOME, "platforms")
                        if os.path.exists(local_platforms):
                            target_dir = os.path.join(local_platforms, f"android-{sdk_ver}")
                            if not (os.path.exists(target_dir) and self.is_valid_platform(target_dir)):
                                self.log(f"   ⚠️ 警告：本地缺少有效的 android-{sdk_ver}，请去右侧下载或检查！")
                    pkg_match = re.search(r'applicationId\s*[=\s]\s*[\'"]([^\'"]+)[\'"]', content)
                    if pkg_match: self.log(f"   ▸ 包名: {pkg_match.group(1)}")
                    ver_name_match = re.search(r'versionName\s*[=\s]\s*[\'"]([^\'"]+)[\'"]', content)
                    if ver_name_match: self.log(f"   ▸ 版本名称: {ver_name_match.group(1)}")
            except Exception as e:
                self.log(f"⚠️ 读取失败: {str(e)}")
        self.log("✅ 项目深度分析完成。")

    def start_decompile(self):
        apk_path = self.decompile_path_var.get()
        if not apk_path or not os.path.exists(apk_path):
            messagebox.showwarning("提示", "请先选择要反编译的 APK 文件！")
            return
        if not os.path.exists(self.JADX_PATH):
            self.log(f"❌ 反编译失败：找不到 jadx 工具！")
            messagebox.showerror("缺少工具", "未找到 jadx 反编译工具。\n\n请将 jadx 工具放入 tools/jadx 目录下。")
            return
        out_dir = filedialog.askdirectory(title="选择反编译代码保存的目录")
        if not out_dir: return
        self.log(f"\n🛠️ 开始反编译 APK: {apk_path}")
        self.log(f"📂 输出目录: {out_dir}")
        self.log("⏳ 请稍候，反编译可能需要几十秒到几分钟...")
        threading.Thread(target=self._execute_decompile, args=(apk_path, out_dir), daemon=True).start()

    def _execute_decompile(self, apk_path, out_dir):
        try:
            cmd = [self.JADX_PATH, "-d", out_dir, apk_path]
            env = self.get_green_env()
            process = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=True)
            self.active_processes.append(process)
            
            for line in process.stdout: self.log(line.strip())
            process.wait()
            
            if process in self.active_processes: self.active_processes.remove(process)
            
            if process.returncode == 0:
                self.log("✅ 反编译成功！")
                self.log(f"👉 请前往 {out_dir} 目录查看源码（sources 文件夹下为 Java 代码）。")
                os.startfile(out_dir)
            else:
                self.log("❌ 反编译失败，请查看上方日志。")
        except Exception as e:
            self.log(f"发生异常: {str(e)}")

    def start_build(self):
        project_path = self.project_path_var.get()
        if not project_path:
            messagebox.showwarning("提示", "请先选择工程文件夹")
            return
            
        self.prepare_local_gradle(project_path)

        if self.enable_sign_var.get():
            if not self.ks_path_var.get() or not os.path.exists(self.ks_path_var.get()):
                messagebox.showerror("错误", "已勾选签名，但未找到有效的 .jks 密钥文件！")
                return
            if not self.ks_pass_var.get() or not self.alias_var.get() or not self.key_pass_var.get():
                messagebox.showerror("错误", "请完整填写签名密码和别名信息！")
                return

        self.is_busy = True
        self.build_btn.config(state="disabled", text="⏳ 正在全量编译中，请稍候...")
        self.log("\n========== 开始全量编译 APK (Clean & Build) ==========")
        threading.Thread(target=self._execute_build, args=(project_path, self.output_path_var.get()), daemon=True).start()

    def _execute_build(self, project_path, output_path):
        try:
            gradlew_path = os.path.join(project_path, "gradlew.bat" if os.name == 'nt' else "gradlew")
            is_release = self.enable_sign_var.get()
            build_task = "clean assembleRelease --no-daemon" if is_release else "clean assembleDebug --no-daemon"
            
            local_props_path = os.path.join(project_path, "local.properties")
            with open(local_props_path, "w", encoding="utf-8") as f:
                f.write(f"sdk.dir={self.SDK_HOME.replace('\\', '\\\\')}\n")

            self.log(f"正在执行全量编译: gradlew {build_task} ...")
            env = self.get_green_env()

            process = subprocess.Popen(
                [gradlew_path] + build_task.split(" "),
                cwd=project_path, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=True
            )
            self.active_processes.append(process)

            for line in process.stdout: self.log(line.strip())
            process.wait()

            if process in self.active_processes: self.active_processes.remove(process)

            if process.returncode == 0:
                self.log("✅ 全量编译成功！")
                if is_release:
                    base_apk = os.path.join(project_path, "app", "build", "outputs", "apk", "release", "app-release-unsigned.apk")
                    if not os.path.exists(base_apk):
                        base_apk = os.path.join(project_path, "app", "build", "outputs", "apk", "release", "app-release.apk")
                    self._process_release_apk(base_apk, output_path)
                else:
                    base_apk = os.path.join(project_path, "app", "build", "outputs", "apk", "debug", "app-debug.apk")
                    self._copy_apk(base_apk, output_path, "debug")
            else:
                self.log("❌ 编译失败，请查看上方日志。")
        except Exception as e:
            self.log(f"发生异常: {str(e)}")
        finally:
            self.is_busy = False
            self.root.after(0, lambda: self.build_btn.config(state="normal", text="全量编译并输出 APK"))

    def _process_release_apk(self, apk_path, output_path):
        if not os.path.exists(apk_path):
            self.log(f"⚠️ 找不到 Release APK 文件: {apk_path}")
            return
        if not self.enable_sign_var.get():
            self._copy_apk(apk_path, output_path, "release-unsigned")
            return

        self.log("✍️ 开始使用自定义密钥签名 APK...")
        build_tools_dir = os.path.join(self.SDK_HOME, "build-tools")
        apksigner_path = None
        if os.path.exists(build_tools_dir):
            versions = sorted(os.listdir(build_tools_dir), reverse=True)
            for ver in versions:
                potential_path = os.path.join(build_tools_dir, ver, "apksigner.bat")
                if os.path.exists(potential_path):
                    apksigner_path = potential_path
                    break
        
        if not apksigner_path:
            self.log("❌ 找不到 apksigner 工具，请在 SDK 中安装 build-tools。")
            return

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        signed_apk_path = os.path.join(output_path, f"app-release-signed_{timestamp}.apk")

        cmd = [
            apksigner_path, "sign",
            "--ks", self.ks_path_var.get(),
            "--ks-pass", f"pass:{self.ks_pass_var.get()}",
            "--key-pass", f"pass:{self.key_pass_var.get()}",
            "--ks-key-alias", self.alias_var.get(),
            "--out", signed_apk_path,
            apk_path
        ]

        env = self.get_green_env()
        process = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=True)
        self.active_processes.append(process)
        
        for line in process.stdout: self.log(line.strip())
        process.wait()

        if process in self.active_processes: self.active_processes.remove(process)

        if process.returncode == 0:
            self.log(f"📦 签名成功！APK 已保存至: {signed_apk_path}")
        else:
            self.log("❌ 签名失败，请检查密码或 Alias 是否正确。")

    def _copy_apk(self, apk_src, output_path, suffix):
        if not output_path: output_path = self.DESKTOP_DIR
        if os.path.exists(apk_src):
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            dest_file = os.path.join(output_path, f"app-{suffix}_{timestamp}.apk")
            shutil.copy(apk_src, dest_file)
            self.log(f"📦 成功！APK 已输出到: {dest_file}")
        else:
            self.log(f"⚠️ 找不到生成的 APK 文件: {apk_src}")

    def start_install_sdk(self):
        if not os.path.exists(self.SDK_MANAGER):
            messagebox.showerror("错误", "找不到 sdkmanager.bat。")
            return
        component = self.sdk_combo.get()
        self.is_busy = True
        self.current_downloading_component = component 
        self.log(f"\n⬇️ 开始下载组件: {component} ...")
        threading.Thread(target=self._install_sdk_task, args=(component,), daemon=True).start()

    def _install_sdk_task(self, component):
        env = self.get_green_env()
        cmd = [self.SDK_MANAGER, f"--sdk_root={self.SDK_HOME}", component]
        
        try:
            process = subprocess.Popen(cmd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=True)
            self.active_processes.append(process)
            
            process.stdin.write("y\n" * 10)
            process.stdin.flush()
            
            printed_urls = set()
            has_printed_installing = False
            
            ignore_patterns = [
                r"Warning: Observed package id",
                r"Loading local repository",
                r"Fetch remote repository",
                r"Computing updates",
                r"Loading package information",
                r"\[=*\s*\]" 
            ]

            for line in process.stdout:
                raw_line = line.strip()
                if not raw_line: continue
                if any(re.search(p, raw_line) for p in ignore_patterns): continue

                if "Downloading" in raw_line:
                    match = re.search(r'Downloading\s+([^\s]+)', raw_line)
                    if match:
                        filename = match.group(1).replace('\r', '').strip()
                        if not filename.endswith('.zip'): filename += '.zip'
                        download_url = f"https://dl.google.com/android/repository/{filename}"
                        
                        if download_url not in printed_urls:
                            self.log("\n" + "="*60)
                            self.log(f"👉 【极速下载通道】请复制以下链接到浏览器下载:")
                            self.log(download_url)
                            self.log("="*60 + "\n")
                            self.log(f"提示: 下载完成后，将 .zip 包放入 {os.path.basename(self.OFFLINE_DIR)} 目录即可自动安装！")
                            printed_urls.add(download_url)
                    continue
                
                if "Unzipping" in raw_line or "Installing" in raw_line:
                    if not has_printed_installing:
                        self.log("正在本地解压和安装组件，请稍候...")
                        has_printed_installing = True
                    
            process.wait()
            if process in self.active_processes: self.active_processes.remove(process)
            
            if process.returncode == 0:
                self.log(f"✅ 组件 {component} 安装成功！")
                self.root.after(0, self.update_sdk_status_ui)
            else:
                self.log(f"❌ 组件 {component} 安装失败。请复制上方链接手动下载并放入离线包目录。")
        except Exception as e:
            self.log(f"下载异常: {str(e)}")
        finally:
            self.is_busy = False
            self.current_downloading_component = None

if __name__ == "__main__":
    try:
        root = ttk.Window(themename="cosmo")
        app = GreenBuildApp(root)
        root.mainloop()
    except Exception as e:
        error_msg = traceback.format_exc()
        with open("crash_log.txt", "w", encoding="utf-8") as f:
            f.write(error_msg)
        try:
            import tkinter.messagebox as msg
            msg.showerror("程序启动失败", f"发生严重错误，程序无法启动：\n\n{str(e)}\n\n详情请查看目录下的 crash_log.txt 文件。")
        except:
            pass
