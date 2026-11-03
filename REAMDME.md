# 📱 GreenBuild - 安卓全绿色编译与签名工具 (v1.2.7)

**GreenBuild** 是一款基于 Python 和 `ttkbootstrap` 开发的**纯绿色、免安装、零污染**的安卓图形化编译工具。它专为不熟悉复杂命令行配置的开发者、需要快速修改或重打包 APK 的用户设计。

**无需在电脑全局安装 JDK 和 Android SDK**，所有依赖、缓存、临时文件均被严格隔离在软件所在目录下，真正做到“解压即用，删文件夹即卸载”，绝不污染 C 盘环境。

---

## ✨ 核心特性

*   🔒 **极致绿色隔离**：自带 JDK、SDK、Gradle 缓存，绝不篡改系统环境变量，`TEMP`、`ADB` 密钥全部隔离在本地。
*   📦 **离线包自动解压装配**：只需将下载的 `.zip` 丢进指定文件夹，软件启动时自动解压并配置（支持 Platform、Build-tools、Gradle）。
*   🚀 **一键全量编译**：自动执行 `clean assembleDebug/Release --no-daemon`，跳过缓存并强制清理后台 Java 守护进程。
*   🔍 **深度项目分析**：自动读取工程 `build.gradle`，解析包名、版本号、编译 SDK，并智能提示缺失组件。
*   🔏 **多套签名配置**：支持保存多套 `.jks` 签名信息（密码本地 Base64 加密），一键切换，免去重复输入。
*   🛠️ **APK 一键反编译**：内置调用 `jadx`，快速逆向 APK 找回 Java 源码和资源文件。
*   🧹 **进程级大扫除**：关闭软件时，自动按路径精准查杀残留的 `java.exe`、`adb.exe`、`cmd.exe`，解决文件被锁无法复制/删除的问题。
*   🌐 **智能提取下载链接**：当组件下载慢时，自动提取 Google 官方直链，方便复制到浏览器极速下载。

---

## 📂 极重要：目录结构详解

为了软件的正常运行，请确保你的软件根目录拥有以下结构。**带 `[自动]` 的文件夹不需要你创建，软件启动时会自动生成；带 `[手动]` 的必须由你准备。**

```text
GreenBuild/                       # 软件根目录
│
├── GreenBuild.exe                # [手动] 主程序
├── sign_configs.json             # [自动] 保存的签名配置记录 (Base64加密)
│
├── jdk/                          # [手动] Java 运行环境 (JDK 17 或 11)
│   └── bin/
│       └── java.exe              # 必须存在此文件
│
├── sdk/                          # [自动/手动] Android SDK 目录
│   ├── cmdline-tools/            # [手动] 官方命令行工具
│   │   └── latest/               # 必须有 latest 这一层
│   │       └── bin/
│   │           └── sdkmanager.bat
│   ├── platforms/                # [自动/手动] 安卓平台包
│   ├── build-tools/              # [自动/手动] 构建工具
│   └── platform-tools/           # [自动] 包含 adb 等
│
├── tools/                        # [手动] 第三方工具目录
│   └── jadx/                     # 反编译工具
│       └── bin/
│           └── jadx.bat          # 必须有此文件
│
├── offline_packages/             # [自动] 离线压缩包投放目录 (重启软件自动处理)
│
├── gradle_cache/                 # [自动] Gradle 运行缓存与依赖库 (隔离在此)
├── temp_cache/                   # [自动] 软件运行时的临时文件 (隔离在此)
└── android_user_cache/           # [自动] ADB 调试密钥等用户数据 (隔离在此)