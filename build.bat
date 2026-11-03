@echo off
chcp 65001 >nul
title GreenBuild 自动化打包工具
echo ==================================================
echo        GreenBuild 绿色版 一键打包脚本
echo ==================================================
echo.

:: 1. 检查 Python 环境
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python 环境！请先安装 Python。
    pause
    exit /b
)

:: 2. 检查并自动安装美化库 ttkbootstrap
echo [1/4] 正在检查依赖：ttkbootstrap (界面美化库)...
pip show ttkbootstrap >nul 2>&1
if %errorlevel% neq 0 (
    echo       未安装，正在为您自动下载并安装...
    pip install ttkbootstrap -i https://pypi.tuna.tsinghua.edu.cn/simple
) else (
    echo       已安装，跳过。
)

:: 3. 检查并自动安装打包工具 PyInstaller
echo.
echo [2/4] 正在检查依赖：pyinstaller (打包工具)...
pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo       未安装，正在为您自动下载并安装...
    pip install pyinstaller -i https://pypi.tuna.tsinghua.edu.cn/simple
) else (
    echo       已安装，跳过。
)

:: 4. 开始打包
echo.
echo [3/4] 开始打包 GreenBuild.exe ...
echo       注意：如果当前目录下有 icon.ico，将自动添加图标。
echo       打包过程可能需要几分钟，请耐心等待...

:: 判断是否有图标文件，如果有就加上 -i 参数
if exist "icon.ico" (
    pyinstaller -F -w -i icon.ico -n "GreenBuild" green_build.py
) else (
    echo       未检测到 icon.ico，将打包为无图标版本。
    pyinstaller -F -w -n "GreenBuild" green_build.py
)

:: 5. 整理文件
echo.
echo [4/4] 正在整理打包结果...
if exist "dist\GreenBuild.exe" (
    copy "dist\GreenBuild.exe" ".\GreenBuild.exe" >nul
    echo.
    echo ==================================================
    echo 🎉 打包成功！
    echo 请查看当前目录下的 GreenBuild.exe
    echo 记得把它和 jdk、sdk、license.key 放在一起发给别人。
    echo ==================================================
) else (
    echo.
    echo ❌ 打包失败，请查看上方的红色报错信息。
)

:: 清理打包产生的临时缓存文件夹
rmdir /s /q build >nul 2>&1
rmdir /s /q dist >nul 2>&1
del /q GreenBuild.spec >nul 2>&1

echo.
pause