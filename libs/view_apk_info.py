"""
APK包名列表脚本 (增强版)

功能:
- 显示详细执行过程
- 生成日志文件
"""

import os
import sys
import subprocess
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
APK_DIR = os.path.join(SCRIPT_DIR, "apk")
LIBS_DIR = os.path.join(SCRIPT_DIR, "libs")
APKEDITOR_JAR = os.path.join(LIBS_DIR, "APKEditor.jar")

LOG_FILE = os.path.join(SCRIPT_DIR, f"list_packages_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
LOG_CONTENT = []

def log(msg, print_also=True):
    timestamp = datetime.now().strftime('%H:%M:%S')
    log_msg = f"[{timestamp}] {msg}"
    LOG_CONTENT.append(log_msg)
    if print_also:
        print(log_msg)

def log_section(title):
    log("")
    log("=" * 60)
    log(title)
    log("=" * 60)

def save_log(success=True):
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("APK 包名列表工具 - 执行日志\n")
        f.write("=" * 60 + "\n")
        f.write(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"APK目录: {APK_DIR}\n")
        f.write(f"结果: {'成功' if success else '失败'}\n")
        f.write("\n" + "=" * 60 + "\n")
        f.write("执行过程:\n")
        f.write("=" * 60 + "\n")
        for line in LOG_CONTENT:
            f.write(line + "\n")

def find_java():
    log("开始检测Java环境...")
    
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        java_bin = os.path.join(java_home, "bin", "java.exe")
        if os.path.exists(java_bin):
            log(f"找到Java (JAVA_HOME): {java_bin}")
            return java_bin
    
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    for path_dir in path_dirs:
        java_bin = os.path.join(path_dir, "java.exe")
        if os.path.exists(java_bin):
            log(f"找到Java (PATH): {java_bin}")
            return java_bin
    
    common_paths = [
        r"C:\Program Files\Java\bin\java.exe",
        r"C:\Program Files (x86)\Java\bin\java.exe",
        r"C:\Program Files\Common Files\Oracle\Java\javapath_target_1716437\java.exe",
    ]
    for path in common_paths:
        if os.path.exists(path):
            log(f"找到Java (常用路径): {path}")
            return path
    
    return None

def get_apk_info(apk_path, java_bin):
    log(f"正在分析: {apk_path}")
    
    cmd = f'"{java_bin}" -jar "{APKEDITOR_JAR}" info -i "{apk_path}" -package -version-name -version-code'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode != 0:
        log(f"  获取失败: {result.stderr[:100] if result.stderr else '未知错误'}")
        return None, None
    
    output = result.stdout
    package = None
    vn = None
    vc = None
    
    for line in output.split('\n'):
        if line.startswith('package='):
            package = line.split('=')[1].strip()
        elif line.startswith('VersionName='):
            vn = line.split('=')[1].strip()
        elif line.startswith('VersionCode='):
            vc = line.split('=')[1].strip()
    
    if vn and vc:
        version = f"{vn} ({vc})"
    elif vn:
        version = vn
    else:
        version = "Unknown"
    
    log(f"  包名: {package}")
    log(f"  版本: {version}")
    
    return package, version

def main():
    print("=" * 60)
    print("APK 包名列表工具 (增强版)")
    print("=" * 60)
    print(f"日志将保存到: {LOG_FILE}")
    print()
    
    log("工具启动")
    
    log_section("环境检查")
    java_bin = find_java()
    if not java_bin:
        log("错误: 未找到Java", False)
        save_log(False)
        return
    
    log(f"Java: {java_bin}")
    log(f"APKEditor: {APKEDITOR_JAR}")
    
    if not os.path.exists(APK_DIR):
        log(f"错误: 目录不存在: {APK_DIR}", False)
        save_log(False)
        return
    
    log_section("扫描APK文件")
    apk_files = [f for f in os.listdir(APK_DIR) if f.lower().endswith('.apk')]
    log(f"找到 {len(apk_files)} 个APK文件")
    
    if not apk_files:
        log("未找到APK文件", False)
        save_log(True)
        return
    
    log("")
    log(f"{'文件名':<35} {'包名':<40} {'版本':<15}")
    log("-" * 90)
    
    results = []
    for apk_file in sorted(apk_files):
        apk_path = os.path.join(APK_DIR, apk_file)
        apk_size = os.path.getsize(apk_path) / (1024*1024)
        log(f"文件: {apk_file} ({apk_size:.1f} MB)")
        
        package, version = get_apk_info(apk_path, java_bin)
        
        if package:
            log(f"  => {package} | {version}")
            results.append((apk_file, package, version))
        else:
            log(f"  => 获取失败")
            results.append((apk_file, "获取失败", ""))
    
    log("-" * 90)
    log(f"共 {len(apk_files)} 个APK")
    log(f"日志已保存: {LOG_FILE}")
    
    save_log(True)
    
    log("")
    log("=" * 60)
    log("执行完成!")
    log("=" * 60)
    log("按回车键退出...")
    try:
        input()
    except:
        pass

if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        save_log(False)
    except Exception as e:
        save_log(False)
        try:
            input()
        except:
            pass