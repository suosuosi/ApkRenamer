"""
APK包名一键替换脚本 (增强版)

功能:
- 显示详细执行过程
- 生成日志文件
- 检测加壳等不支持的情况
"""

import os
import sys
import subprocess
import shutil
from datetime import datetime
from multiprocessing import Pool, cpu_count

# ============================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
APK_DIR = os.path.join(SCRIPT_DIR, "apk")
# INPUT_APK 不再使用，改由用户选择
OUTPUT_APK_TEMP = os.path.join(APK_DIR, "output_temp.apk")

LIBS_DIR = os.path.join(SCRIPT_DIR, "libs")
APKEDITOR_JAR = os.path.join(LIBS_DIR, "APKEditor.jar")
UBER_APK_SIGNER = os.path.join(LIBS_DIR, "uber-apk-signer.jar")
KEYSTORE = os.path.join(LIBS_DIR, "debug.keystore")

# 日志目录
LOG_DIR = os.path.join(SCRIPT_DIR, "log")
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

LOG_FILE = os.path.join(LOG_DIR, f"repackage_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
LOG_CONTENT = []

# 全局变量
NEW_PACKAGE = ""
input_apk_path = ""

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

def save_log(success=True, error_msg=""):
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("APK 包名替换工具 - 执行日志\n")
        f.write("=" * 60 + "\n")
        f.write(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"输入文件: {input_apk_path if input_apk_path else 'N/A'}\n")
        f.write(f"目标包名: {NEW_PACKAGE}\n")
        f.write(f"结果: {'成功' if success else '失败'}\n")
        if error_msg:
            f.write(f"错误信息: {error_msg}\n")
        f.write("\n" + "=" * 60 + "\n")
        f.write("执行过程:\n")
        f.write("=" * 60 + "\n")
        for line in LOG_CONTENT:
            f.write(line + "\n")
        
        if not success:
            f.write("\n" + "=" * 60 + "\n")
            f.write("错误详情:\n")
            f.write("=" * 60 + "\n")
            f.write(error_msg + "\n")

def load_package_names():
    """从 name.txt 加载包名列表"""
    name_file = os.path.join(SCRIPT_DIR, "name.txt")
    packages = []
    
    if not os.path.exists(name_file):
        return packages
    
    with open(name_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    current_desc = ""
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # 如果是注释行（以#开头），记录描述
        if line.startswith('#'):
            current_desc = line[1:].strip()
            continue
        
        # 否则是包名 (移除所有空白字符)
        package_name = line.strip()
        # 移除所有空白字符（包括空格、制表符等）
        package_name = ''.join(package_name.split())
        if package_name:
            packages.append({
                'name': package_name,
                'desc': current_desc if current_desc else package_name
            })
            current_desc = ""
    
    return packages

def scan_apk_files():
    """扫描 apk 目录下的所有 APK 文件"""
    apk_files = []
    
    if not os.path.exists(APK_DIR):
        return apk_files
    
    for filename in os.listdir(APK_DIR):
        if filename.lower().endswith('.apk'):
            filepath = os.path.join(APK_DIR, filename)
            if os.path.isfile(filepath):
                apk_files.append({
                    'filename': filename,
                    'filepath': filepath,
                    'size': os.path.getsize(filepath) / (1024 * 1024)  # MB
                })
    
    return apk_files

def select_apk():
    """让用户选择 APK 文件"""
    apk_files = scan_apk_files()
    
    if not apk_files:
        print("错误: apk 目录下未找到 APK 文件")
        print("")
        print("请将待处理的 APK 文件放入 apk/ 目录，然后重新运行脚本")
        print("按回车键退出...")
        try:
            input()
        except:
            pass
        sys.exit(0)
    
    print("\n" + "=" * 50)
    print("请选择要处理的 APK:")
    print("=" * 50)
    
    for i, apk in enumerate(apk_files, 1):
        # 显示文件名和大小
        filename = apk['filename']
        size = apk['size']
        print(f"  {i}. {filename} ({size:.1f} MB)")
    
    print("=" * 50)
    
    while True:
        try:
            choice = input("请输入序号 (直接回车使用第一个): ").strip()
            if not choice:
                return apk_files[0]['filepath']
            
            idx = int(choice)
            if 1 <= idx <= len(apk_files):
                return apk_files[idx - 1]['filepath']
            else:
                print(f"请输入 1-{len(apk_files)} 之间的数字")
        except ValueError:
            print("请输入有效的数字")

def select_package():
    """让用户选择包名"""
    packages = load_package_names()
    
    if not packages:
        print("错误: 未找到可用的包名，请检查 name.txt 文件")
        print("按回车键退出...")
        try:
            input()
        except:
            pass
        sys.exit(0)
    
    print("\n" + "=" * 50)
    print("请选择要替换的包名:")
    print("=" * 50)
    
    for i, pkg in enumerate(packages, 1):
        desc = pkg['desc'] if pkg['desc'] != pkg['name'] else ""
        if desc:
            print(f"  {i}. {pkg['name']} ({desc})")
        else:
            print(f"  {i}. {pkg['name']}")
    
    print("=" * 50)
    
    while True:
        try:
            choice = input("请输入序号 (直接回车使用第一个): ").strip()
            if not choice:
                return packages[0]['name']
            
            idx = int(choice)
            if 1 <= idx <= len(packages):
                return packages[idx - 1]['name']
            else:
                print(f"请输入 1-{len(packages)} 之间的数字")
        except ValueError:
            print("请输入有效的数字")

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

def check_environment():
    log_section("环境检查")
    errors = []
    
    java_bin = find_java()
    if not java_bin:
        errors.append("错误: 未找到Java，请安装JDK 17+")
    else:
        log("Java环境: OK")
    
    if not os.path.exists(APKEDITOR_JAR):
        errors.append("错误: 未找到 APKEditor.jar")
    else:
        log("APKEditor.jar: OK")
    
    if not os.path.exists(UBER_APK_SIGNER):
        errors.append("错误: 未找到 uber-apk-signer.jar")
    else:
        log("uber-apk-signer.jar: OK")
    
    # 不再检查 input.apk，因为由用户选择
    # APK 文件的检查在选择后进行
    
    if not os.path.exists(KEYSTORE):
        log("未找到debug.keystore，将自动生成...")
        if java_bin:
            keytool_cmd = f'"{java_bin}" -genkeypair -keystore "{KEYSTORE}" -alias androiddebugkey -keyalg RSA -keysize 2048 -validity 10000 -storepass android -keypass android -dname "CN=Android Debug,O=Android,C=US"'
            subprocess.run(keytool_cmd, shell=True, capture_output=True)
            if os.path.exists(KEYSTORE):
                log("debug.keystore: 已生成")
            else:
                errors.append("错误: 无法生成 debug.keystore")
    else:
        log("debug.keystore: OK")
    
    if errors:
        for e in errors:
            log(e, False)
        return None
    
    log("环境检查完成!")
    return java_bin

def run_command(cmd, description):
    log(f"开始执行: {description}")
    log(f"命令: {cmd[:80]}...")
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.stdout:
        for line in result.stdout.split('\n')[:30]:
            if line.strip():
                log(f"  {line}")
    
    if result.returncode == 0:
        log(f"完成: {description} - 成功")
    else:
        log(f"失败: {description} - 返回码 {result.returncode}")
        if result.stderr:
            log(f"错误: {result.stderr[:200]}")
    
    return result.returncode == 0

def check_apk_support(decoded_dir):
    log_section("检查APK支持情况")
    issues = []
    
    smali_dir = os.path.join(decoded_dir, "smali")
    smali_count = 0
    if os.path.exists(smali_dir):
        for root, dirs, files in os.walk(smali_dir):
            smali_count += len([f for f in files if f.endswith('.smali')])
    
    log(f"smali文件数量: {smali_count}")
    
    if smali_count < 50:
        issues.append(f"警告: smali文件数量很少({smali_count}个)，可能是加壳APK!")
        log(f"可能原因: APK使用了代码混淆或加壳保护", False)
    
    dex_cache = os.path.join(decoded_dir, ".cache")
    dex_files = []
    if os.path.exists(dex_cache):
        dex_files = [f for f in os.listdir(dex_cache) if f.endswith('.dex')]
    log(f"DEX文件数量: {len(dex_files)}")
    
    return issues

def get_package_from_manifest(decoded_dir):
    manifest_path = os.path.join(decoded_dir, "AndroidManifest.xml")
    if os.path.exists(manifest_path):
        with open(manifest_path, 'r', encoding='utf-8') as f:
            content = f.read()
            import re
            match = re.search(r'package="([^"]+)"', content)
            if match:
                return match.group(1)
    return None

def pause_with_warning(issues):
    log_section("检测到问题!")
    for issue in issues:
        log(f"  ! {issue}")
    
    log("")
    log("是否继续执行? (可能无法正常工作)")
    log("输入 'y' 继续，或其他键退出: ", False)
    
    try:
        user_input = input().strip().lower()
        if user_input != 'y':
            log("用户取消执行")
            return False
    except:
        return False
    
    return True

def process_single_file(args):
    """
    多进程处理单个文件
    用于步骤3的并行替换
    """
    filepath, old_package, new_package, old_path, new_path, old_prefix, new_prefix = args
    
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        replaced = False
        
        # 替换点分隔的包名
        if old_package in content:
            content = content.replace(old_package, new_package)
            replaced = True
        
        # 替换路径格式的包名
        if old_path in content:
            content = content.replace(old_path, new_path)
            replaced = True
        
        # 替换包名前缀
        if old_prefix and old_prefix in content:
            content = content.replace(old_prefix, new_prefix)
            replaced = True
        
        if replaced:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return 1
        return 0
    except Exception:
        return 0

def main():
    global NEW_PACKAGE, input_apk_path
    
    # 首先让用户选择 APK 文件
    selected_apk = select_apk()
    if not selected_apk:
        print("未选择 APK，程序退出")
        return
    
    # 记录选择的 APK 路径
    input_apk_path = selected_apk
    
    # 然后让用户选择包名
    selected_package = select_package()
    if not selected_package:
        print("未选择包名，程序退出")
        return
    
    NEW_PACKAGE = selected_package
    
    print("=" * 60)
    print("APK 包名替换工具 (增强版)")
    print("=" * 60)
    print(f"日志将保存到: {LOG_FILE}")
    print()
    
    log("工具启动")
    
    java_bin = check_environment()
    if not java_bin:
        save_log(False, "环境检查失败")
        log("环境检查失败，程序退出")
        return
    
    log(f"输入APK: {input_apk_path}")
    log(f"目标包名: {NEW_PACKAGE}")
    
    # 步骤1: 反编译
    log_section("步骤1: 反编译APK")
    work_dir = os.path.join(SCRIPT_DIR, "decoded")
    
    if os.path.exists(work_dir):
        log("清理旧的解码目录...")
        shutil.rmtree(work_dir)
    
    decode_cmd = f'"{java_bin}" -jar "{APKEDITOR_JAR}" decode -i "{input_apk_path}" -o "{work_dir}" -f'
    if not run_command(decode_cmd, "反编译APK"):
        save_log(False, "反编译失败")
        return
    
    log("反编译完成!")
    
    issues = check_apk_support(work_dir)
    if issues:
        if not pause_with_warning(issues):
            save_log(False, "用户取消 - APK可能不被支持")
            return
    
    old_package = get_package_from_manifest(work_dir)
    if not old_package:
        save_log(False, "无法获取APK包名")
        log("错误: 无法获取APK包名")
        return
    
    log(f"检测到原包名: {old_package}")
    log(f"将替换为: {NEW_PACKAGE}")
    
    # 步骤2: 修改AndroidManifest.xml
    log_section("步骤2: 修改AndroidManifest.xml")
    manifest_path = os.path.join(work_dir, "AndroidManifest.xml")
    
    with open(manifest_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    log(f"开始替换包名: {old_package} -> {NEW_PACKAGE}")
    
    # 1. 替换package属性
    content = content.replace(f'package="{old_package}"', f'package="{NEW_PACKAGE}"')
    log("1. 替换package属性")
    
    # 2. 替换所有 android:name 属性值中的旧包名
    content = content.replace(f'android:name="{old_package}.', f'android:name="{NEW_PACKAGE}.')
    log("2. 替换android:name属性")
    
    # 3. 替换所有旧包名的引用 (更彻底的替换)
    content = content.replace(old_package, NEW_PACKAGE)
    log("3. 替换所有旧包名引用")
    
    # 4. 检查并替换 android:authorities 属性
    content = content.replace(f'android:authorities="{old_package}', f'android:authorities="{NEW_PACKAGE}')
    log("4. 替换android:authorities")
    
    # 5. 替换 permission 名称
    content = content.replace(f'android:name="{old_package}.', f'android:name="{NEW_PACKAGE}.')
    log("5. 替换permission名称")
    
    # 替换 android:scheme 中的旧包名
    content = content.replace(f'android:scheme="{old_package.split(".")[0]}', f'android:scheme="{NEW_PACKAGE.split(".")[0]}')
    log("6. 替换android:scheme")
    
    old_count = content.count(NEW_PACKAGE)
    
    with open(manifest_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    log(f"包名替换完成: 新包名出现约 {old_count} 处")

    # 步骤3: 替换所有文件中的包名（多进程并行优化）
    log_section("步骤3: 替换所有文件中的包名")

    old_path = old_package.replace('.', '/')
    new_path = NEW_PACKAGE.replace('.', '/')

    # 提取包名的前缀部分 (如 cn.aqzscn)
    old_package_prefix = '.'.join(old_package.split('.')[:2])
    new_package_prefix = '.'.join(NEW_PACKAGE.split('.')[:2])

    # 要处理的文件扩展名
    extensions = ['.smali', '.xml', '.json', '.prop', '.txt', '.conf', '.ini']

    # 第一步：收集所有需要处理的文件
    log("正在收集需要处理的文件...")
    file_args = []

    for root, dirs, files in os.walk(work_dir):
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext in extensions:
                filepath = os.path.join(root, filename)
                file_args.append((filepath, old_package, NEW_PACKAGE, old_path, new_path, old_package_prefix, new_package_prefix))

    total_files = len(file_args)
    log(f"找到 {total_files} 个需要处理的文件")
    print(f"\n{'=' * 50}")
    print(f"步骤3: 开始替换包名")
    print(f"  - 需要处理: {total_files} 个文件")
    print(f"{'=' * 50}\n")

    # 第二步：计算并行进程数（使用CPU核心数的一半）
    cpu_cores = cpu_count() or 4
    process_count = max(1, cpu_cores // 2)
    log(f"使用 {process_count} 个进程并行处理...")

    # 第三步：多进程并行处理（带进度显示）
    total_replaced = 0
    processed = 0
    last_progress = 0

    # 使用imap_unordered来实时获取进度
    with Pool(process_count) as pool:
        # imap_unordered 返回迭代器，可以实时处理完成的结果
        for result in pool.imap_unordered(process_single_file, file_args, chunksize=50):
            processed += 1
            total_replaced += result

            # 每5%显示一次进度
            progress = int(processed * 100 / total_files)
            if progress - last_progress >= 5 or processed == total_files:
                # 进度条
                bar_length = 30
                filled = int(bar_length * processed / total_files)
                bar = '█' * filled + '░' * (bar_length - filled)
                print(f"  [{bar}] {progress}% ({processed}/{total_files}) 文件")
                last_progress = progress

    print(f"\n{'=' * 50}")
    print(f"步骤3 完成!")
    print(f"  - 总文件数: {total_files}")
    print(f"  - 已替换: {total_replaced} 个文件")
    print(f"  - 使用进程: {process_count}")
    print(f"{'=' * 50}\n")

    log(f"共处理 {total_files} 个文件，替换了 {total_replaced} 个文件")
    
    # 步骤3.5: 重命名smali目录结构 (关键!)
    log_section("步骤3.5: 重命名smali目录结构")
    smali_classes_dir = os.path.join(work_dir, "smali", "classes")
    
    if os.path.exists(smali_classes_dir):
        # 检查是否存在旧包名路径格式的目录
        old_package_parts = old_package.split('.')
        new_package_parts = NEW_PACKAGE.split('.')
        
        # 尝试找到根目录 (如 cn, org, com 等)
        if old_package_parts:
            first_part = old_package_parts[0]
            old_dir = os.path.join(smali_classes_dir, first_part)
            
            if os.path.exists(old_dir):
                log(f"发现旧包名目录: {first_part}")
                
                # 构建新目录路径
                new_dir = os.path.join(smali_classes_dir, new_package_parts[0])
                
                # 如果新路径已存在（可能是重复包名），先删除
                if os.path.exists(new_dir) and new_dir != old_dir:
                    log(f"  警告: 目标目录已存在，将尝试合并或跳过")
                else:
                    # 重命名目录
                    try:
                        # 如果第一部分不同，直接重命名
                        if first_part != new_package_parts[0]:
                            os.rename(old_dir, new_dir)
                            log(f"  重命名目录: {first_part} -> {new_package_parts[0]}")
                        
                        # 处理多级目录结构
                        # 例如: cn/aqzscn/... -> com/xxx/hlddz/...
                        current_old_path = new_dir  # 从新位置开始
                        current_new_path = new_dir
                        
                        for i in range(1, len(old_package_parts)):
                            old_subdir = old_package_parts[i]
                            # 查找当前目录下的旧子目录
                            if os.path.exists(current_old_path):
                                for item in os.listdir(current_old_path):
                                    item_path = os.path.join(current_old_path, item)
                                    if os.path.isdir(item_path) and item == old_subdir:
                                        if i < len(new_package_parts):
                                            new_subdir = new_package_parts[i]
                                            new_subdir_path = os.path.join(current_old_path, new_subdir)
                                            
                                            if item != new_subdir:
                                                os.rename(item_path, new_subdir_path)
                                                log(f"  重命名子目录: {old_subdir} -> {new_subdir}")
                                            
                                            current_new_path = new_subdir_path
                                        break
                        
                        log("smali目录结构重命名完成")
                    except Exception as e:
                        log(f"  目录重命名警告: {str(e)[:100]}")
    
    # 步骤3.6: 更新resources文件中的包名
    log_section("步骤3.6: 更新resources配置文件")
    
    # 更新 public.xml 中的 package 属性
    public_xml_path = os.path.join(work_dir, "resources", "package_1", "res", "values", "public.xml")
    if os.path.exists(public_xml_path):
        try:
            with open(public_xml_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            old_pub_pkg = f'package="{old_package}"'
            new_pub_pkg = f'package="{NEW_PACKAGE}"'
            
            if old_pub_pkg in content:
                content = content.replace(old_pub_pkg, new_pub_pkg)
                with open(public_xml_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                log(f"更新 public.xml package属性")
        except Exception as e:
            log(f"  更新public.xml警告: {str(e)[:50]}")
    
    # 更新 package.json 中的 package_name
    package_json_path = os.path.join(work_dir, "resources", "package_1", "package.json")
    if os.path.exists(package_json_path):
        try:
            import json
            with open(package_json_path, 'r', encoding='utf-8') as f:
                pkg_data = json.load(f)
            
            if pkg_data.get('package_name') == old_package:
                pkg_data['package_name'] = NEW_PACKAGE
                with open(package_json_path, 'w', encoding='utf-8') as f:
                    json.dump(pkg_data, f, indent=2, ensure_ascii=False)
                log(f"更新 package.json package_name")
        except Exception as e:
            log(f"  更新package.json警告: {str(e)[:50]}")
    
    # 步骤4: 重新打包
    log_section("步骤4: 重新打包APK")
    if os.path.exists(OUTPUT_APK_TEMP):
        os.remove(OUTPUT_APK_TEMP)
    
    build_cmd = f'"{java_bin}" -jar "{APKEDITOR_JAR}" build -i "{work_dir}" -o "{OUTPUT_APK_TEMP}" -f'
    if not run_command(build_cmd, "打包APK"):
        save_log(False, "打包失败")
        return
    
    # 步骤5: 签名
    log_section("步骤5: 签名APK")
    sign_cmd = f'"{java_bin}" -jar "{UBER_APK_SIGNER}" --apks "{OUTPUT_APK_TEMP}" --ks "{KEYSTORE}" --ksPass android --ksAlias androiddebugkey --ksKeyPass android --out "{APK_DIR}"'
    if not run_command(sign_cmd, "签名APK"):
        save_log(False, "签名失败")
        return
    
    # 查找签名后的APK
    signed_apk = os.path.join(APK_DIR, "output_temp-aligned-signed.apk")
    # 命名规则: 原包名最后两位 + 新包名最后两位 + 时间戳
    old_last_two = '.'.join(old_package.split('.')[-2:])  # e.g. douyu.android
    new_last_two = '.'.join(NEW_PACKAGE.split('.')[-2:])  # e.g. smile.gifmaker
    timestamp = datetime.now().strftime('%y%m%d%H%M')  # e.g. 2605071042
    final_apk = os.path.join(APK_DIR, f"{old_last_two}_{new_last_two}_{timestamp}.apk")
    
    if os.path.exists(signed_apk):
        if os.path.exists(final_apk):
            os.remove(final_apk)
        os.rename(signed_apk, final_apk)
        
        log_section("步骤6: 验证结果")
        info_cmd = f'"{java_bin}" -jar "{APKEDITOR_JAR}" info -i "{final_apk}" -package -version-name -version-code'
        run_command(info_cmd, "查看APK信息")
        
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir)
            log("清理解码目录完成")
        if os.path.exists(OUTPUT_APK_TEMP):
            os.remove(OUTPUT_APK_TEMP)
        
        log_section("执行完成!")
        log(f"输出APK: {final_apk}")
        log(f"日志文件: {LOG_FILE}")
        
        save_log(True)
    else:
        save_log(False, "未找到签名的APK文件")
        log("未找到签名的APK文件", False)
    
    log("")
    log("=" * 60)
    log("执行完成! 请查看上方结果")
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
        save_log(False, "用户中断执行")
    except Exception as e:
        save_log(False, str(e))
        log(f"执行出错: {e}", False)
        try:
            input()
        except:
            pass