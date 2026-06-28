"""
APK 反编译 / 修改包名 / 编译签名工具
- 反编译: 选择 apk/ 下的 APK，解码到 decoded/<同名>/ 目录
- 修改包名: 选择 decoded/ 下的目录，根据 name.txt 修改包名
- 编译: 选择 decoded/ 下的目录，编译签名输出到 output/ 目录（带时间戳）
"""

import os
import sys
import re
import json
import shutil
import subprocess
from datetime import datetime
from multiprocessing import Pool, cpu_count, freeze_support

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
APK_DIR = os.path.join(SCRIPT_DIR, "apk")
DECODED_DIR = os.path.join(SCRIPT_DIR, "decoded")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")
LIBS_DIR = os.path.join(SCRIPT_DIR, "libs")
APKEDITOR_JAR = os.path.join(LIBS_DIR, "APKEditor.jar")
UBER_APK_SIGNER = os.path.join(LIBS_DIR, "uber-apk-signer.jar")
KEYSTORE = os.path.join(LIBS_DIR, "debug.keystore")


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def find_java():
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        java_bin = os.path.join(java_home, "bin", "java.exe")
        if os.path.exists(java_bin):
            return java_bin
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    for path_dir in path_dirs:
        java_bin = os.path.join(path_dir, "java.exe")
        if os.path.exists(java_bin):
            return java_bin
    common_paths = [
        r"C:\Program Files\Java\bin\java.exe",
        r"C:\Program Files (x86)\Java\bin\java.exe",
        r"C:\Program Files\Common Files\Oracle\Java\javapath_target_1716437\java.exe",
    ]
    for path in common_paths:
        if os.path.exists(path):
            return path
    return None


def scan_apk_files():
    apk_files = []
    if not os.path.exists(APK_DIR):
        return apk_files
    for f in os.listdir(APK_DIR):
        path = os.path.join(APK_DIR, f)
        if f.lower().endswith('.apk') and os.path.isfile(path):
            apk_files.append({
                'filename': f,
                'filepath': path,
                'size': os.path.getsize(path) / (1024 * 1024),
                'name_no_ext': os.path.splitext(f)[0]
            })
    return apk_files


def scan_decoded_dirs():
    dirs = []
    if not os.path.exists(DECODED_DIR):
        return dirs
    for name in sorted(os.listdir(DECODED_DIR)):
        path = os.path.join(DECODED_DIR, name)
        if os.path.isdir(path):
            dirs.append({'name': name, 'path': path})
    return dirs


def choose_item(items, title, prompt="请输入序号 (直接回车使用第一个): "):
    print(f"\n{'=' * 50}")
    print(title)
    print('=' * 50)
    for i, item in enumerate(items, 1):
        print(f"  {i}. {item['label']}")
    print('=' * 50)
    while True:
        try:
            choice = input(prompt).strip()
            if not choice:
                return items[0]
            idx = int(choice)
            if 1 <= idx <= len(items):
                return items[idx - 1]
            print(f"请输入 1-{len(items)} 之间的数字")
        except ValueError:
            print("请输入有效的数字")


def check_environment(java_bin):
    errors = []
    if not java_bin:
        errors.append("未找到 Java，请安装 JDK 17+")
    if not os.path.exists(APKEDITOR_JAR):
        errors.append("未找到 APKEditor.jar")
    if not os.path.exists(UBER_APK_SIGNER):
        errors.append("未找到 uber-apk-signer.jar")
    if not os.path.exists(KEYSTORE):
        log("未找到 debug.keystore，尝试自动生成...")
        if java_bin:
            cmd = f'"{java_bin}" -genkeypair -keystore "{KEYSTORE}" -alias androiddebugkey -keyalg RSA -keysize 2048 -validity 10000 -storepass android -keypass android -dname "CN=Android Debug,O=Android,C=US"'
            subprocess.run(cmd, shell=True, capture_output=True)
        if not os.path.exists(KEYSTORE):
            errors.append("无法生成 debug.keystore")
    if errors:
        for e in errors:
            log(f"错误: {e}")
        return False
    return True


def run_cmd(cmd, desc):
    log(f"{desc}...")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.stdout:
        for line in result.stdout.strip().split('\n')[:20]:
            if line.strip():
                print(f"  {line}")
    if result.returncode != 0:
        log(f"失败: {result.stderr[:300] if result.stderr else '未知错误'}")
        return False
    log(f"{desc} 完成")
    return True


def get_package_from_manifest(decoded_path):
    manifest = os.path.join(decoded_path, "AndroidManifest.xml")
    if os.path.exists(manifest):
        with open(manifest, 'r', encoding='utf-8') as f:
            content = f.read()
        match = re.search(r'package="([^"]+)"', content)
        if match:
            return match.group(1)
    return None


def detect_class_prefix(decoded_path):
    """从 AndroidManifest.xml 中检测 app 自身的类前缀（排除第三方库和权限名）"""
    manifest = os.path.join(decoded_path, "AndroidManifest.xml")
    if not os.path.exists(manifest):
        return None
    lib_prefixes = ('android.', 'androidx.', 'com.google.', 'com.android.',
                    'com.alipay.', 'com.tencent.', 'com.baidu.', 'com.umeng.',
                    'kotlin.', 'kotlinx.', 'com.google.android.gms.',
                    'com.android.billing', 'com.google.android.datatransport.',
                    'com.google.android.play.')
    with open(manifest, 'r', encoding='utf-8') as f:
        content = f.read()
    pkg_match = re.search(r'package="([^"]+)"', content)
    old_package = pkg_match.group(1) if pkg_match else None

    names = re.findall(r'android:name="([^"]+)"', content)
    # Java 类名：标准格式、首字母大写、非全大写（排除常量）
    app_classes = [n for n in names
                   if not n.startswith(lib_prefixes) and '.' in n
                   and ':' not in n
                   and re.match(r'[A-Z][a-zA-Z0-9$]*$', n.split('.')[-1])
                   and not n.split('.')[-1].isupper()]
    if not app_classes:
        return old_package

    # 策略1：优先找包名下的类（如 cn.aqzscn.stream_music.MainActivity → cn.aqzscn.stream_music）
    if old_package:
        pkg_prefix = old_package + '.'
        own = [n for n in app_classes if n.startswith(pkg_prefix)]
        if own:
            prefix = os.path.commonprefix([c + '.' for c in own]).rstrip('.')
            if prefix:
                return prefix

    # 策略2：找同前两段的类（排除 alipay 等第三方，找到 com.jiangdg.demo 这种正确前缀）
    if old_package:
        first_two = '.'.join(old_package.split('.')[:2])
        same_first = [n for n in app_classes if n.startswith(first_two + '.')]
        if same_first:
            prefix = os.path.commonprefix([c + '.' for c in same_first]).rstrip('.')
            if prefix and '.' in prefix and len(prefix.split('.')) >= 2:
                return prefix

    # 回退：用包名本身
    return old_package


def compute_new_class_prefix(old_class_prefix, old_package, new_package):
    """计算新的类路径前缀，正确处理包层级差异"""
    old_parts = old_package.split('.')
    new_parts = new_package.split('.')
    old_class_parts = old_class_prefix.split('.')
    extra = max(0, len(old_parts) - len(new_parts))
    replace_count = max(0, len(old_class_parts) - extra)
    replace_count = min(replace_count, len(new_parts))
    new_class_parts = new_parts[:replace_count] + old_class_parts[replace_count:]
    return '.'.join(new_class_parts)


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
        if line.startswith('#'):
            current_desc = line[1:].strip()
            continue
        package_name = ''.join(line.split())
        if package_name:
            packages.append({
                'name': package_name,
                'desc': current_desc if current_desc else package_name
            })
            current_desc = ""
    return packages


def select_package():
    """让用户选择包名"""
    packages = load_package_names()
    if not packages:
        print("错误: 未找到可用的包名，请检查 name.txt 文件")
        return None
    items = []
    for pkg in packages:
        desc = pkg['desc'] if pkg['desc'] != pkg['name'] else ""
        label = f"{pkg['name']} ({desc})" if desc else pkg['name']
        items.append({'label': label, 'value': pkg['name']})
    return choose_item(items, "请选择要替换的包名:")['value']


def _replace_worker(args):
    filepath, old_package, new_package, old_path, new_path, old_prefix_dot, new_prefix_dot, old_smali_prefix, new_smali_prefix = args
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        original = content
        content = content.replace(old_package, new_package)
        content = content.replace(old_path, new_path)
        if old_prefix_dot:
            content = content.replace(old_prefix_dot, new_prefix_dot)
        if old_smali_prefix:
            content = content.replace(old_smali_prefix, new_smali_prefix)
        if content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return 1
        return 0
    except:
        return 0


def _replace_pkg_only_worker(args):
    filepath, old_package, new_package, old_path, new_path = args
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        original = content
        content = content.replace(old_package, new_package)
        content = content.replace(old_path, new_path)
        if content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return 1
        return 0
    except:
        return 0


def modify_package(decoded_path, new_package):
    """修改解码目录中的包名"""
    log(f"开始修改包名，目标: {new_package}")

    old_package = get_package_from_manifest(decoded_path)
    if not old_package:
        log("错误: 无法获取原包名")
        return False

    log(f"原包名: {old_package}")

    # 检测类路径前缀
    old_class_prefix = detect_class_prefix(decoded_path)
    if not old_class_prefix:
        log("警告: 无法自动检测类路径前缀，使用包名作为类路径")
        old_class_prefix = old_package
    log(f"类路径前缀: {old_class_prefix}")

    new_class_prefix = compute_new_class_prefix(old_class_prefix, old_package, new_package)
    log(f"新类路径前缀: {new_class_prefix}")

    old_smali_prefix = old_class_prefix.replace('.', '/')
    new_smali_prefix = new_class_prefix.replace('.', '/')

    # 1. 修改 AndroidManifest.xml
    log("修改 AndroidManifest.xml...")
    manifest_path = os.path.join(decoded_path, "AndroidManifest.xml")
    with open(manifest_path, 'r', encoding='utf-8') as f:
        content = f.read()

    content = content.replace(f'package="{old_package}"', f'package="{new_package}"')
    content = content.replace(old_package, new_package)
    content = content.replace(f'android:authorities="{old_package}', f'android:authorities="{new_package}')

    with open(manifest_path, 'w', encoding='utf-8') as f:
        f.write(content)
    log("AndroidManifest.xml 修改完成")

    # 2. 替换所有文件中的包名
    log("替换文件中的包名引用...")
    old_path = old_package.replace('.', '/')
    new_path = new_package.replace('.', '/')
    old_prefix_dot = '.'.join(old_package.split('.')[:2])
    new_prefix_dot = '.'.join(new_package.split('.')[:2])

    extensions = ('.smali', '.xml', '.json', '.prop', '.txt', '.conf', '.ini')
    file_args = []
    for root, dirs, files in os.walk(decoded_path):
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext not in extensions:
                continue
            filepath = os.path.join(root, filename)
            file_args.append((filepath, old_package, new_package, old_path, new_path,
                              old_prefix_dot, new_prefix_dot, old_smali_prefix, new_smali_prefix))

    total_files = len(file_args)
    log(f"找到 {total_files} 个文件，多进程替换中...")
    processes = max(1, cpu_count() // 2) if cpu_count() else 4
    replaced_count = 0
    with Pool(processes) as pool:
        for i, result in enumerate(pool.imap_unordered(_replace_worker, file_args, chunksize=50)):
            replaced_count += result
            if (i + 1) % max(1, total_files // 20) == 0 or i + 1 == total_files:
                pct = (i + 1) * 100 // total_files
                bar = '#' * (pct // 5) + '.' * (20 - pct // 5)
                print(f"  [{bar}] {pct}% ({i+1}/{total_files})", flush=True)

    log(f"处理 {total_files} 个文件，替换 {replaced_count} 个文件")

    # 3. 重命名 smali 目录结构
    log("重命名 smali 目录结构...")
    old_smali_parts = old_smali_prefix.split('/')
    new_smali_parts = new_smali_prefix.split('/')
    smali_base = os.path.join(decoded_path, "smali")

    if os.path.exists(smali_base):
        for sub_dir in os.listdir(smali_base):
            smali_sub = os.path.join(smali_base, sub_dir)
            if not os.path.isdir(smali_sub):
                continue
            cur_dir = smali_sub
            renamed = False
            for i in range(len(old_smali_parts)):
                if i >= len(new_smali_parts):
                    break
                old_part = old_smali_parts[i]
                new_part = new_smali_parts[i]
                if old_part == new_part:
                    cur_dir = os.path.join(cur_dir, old_part)
                    if not os.path.exists(cur_dir):
                        break
                    continue
                old_sub = os.path.join(cur_dir, old_part)
                new_sub = os.path.join(cur_dir, new_part)
                if os.path.exists(old_sub):
                    if os.path.exists(new_sub):
                        for child in os.listdir(old_sub):
                            src = os.path.join(old_sub, child)
                            dst = os.path.join(new_sub, child)
                            if os.path.isdir(src):
                                shutil.copytree(src, dst, dirs_exist_ok=True)
                                shutil.rmtree(src)
                            else:
                                shutil.copy2(src, dst)
                                os.remove(src)
                        os.rmdir(old_sub)
                        log(f"  合并: {old_part} -> {new_part}")
                        renamed = True
                    else:
                        os.rename(old_sub, new_sub)
                        log(f"  重命名: {old_part} -> {new_part}")
                        renamed = True
                cur_dir = new_sub if os.path.exists(new_sub) else cur_dir
            if renamed:
                log(f"  {sub_dir}/ 目录重命名完成")

        # 清理空目录
        for sub_dir in os.listdir(smali_base):
            smali_sub = os.path.join(smali_base, sub_dir)
            if not os.path.isdir(smali_sub):
                continue
            for root, dirs, files in os.walk(smali_sub, topdown=False):
                for d in dirs:
                    dir_path = os.path.join(root, d)
                    try:
                        if not os.listdir(dir_path):
                            os.rmdir(dir_path)
                    except:
                        pass

    # 4. 更新 resources 配置
    public_xml = os.path.join(decoded_path, "resources", "package_1", "res", "values", "public.xml")
    if os.path.exists(public_xml):
        try:
            with open(public_xml, 'r', encoding='utf-8') as f:
                content = f.read()
            old_pub = f'package="{old_package}"'
            new_pub = f'package="{new_package}"'
            if old_pub in content:
                content = content.replace(old_pub, new_pub)
                with open(public_xml, 'w', encoding='utf-8') as f:
                    f.write(content)
                log("更新 public.xml")
        except Exception as e:
            log(f"  更新 public.xml 跳过: {e}")

    pkg_json = os.path.join(decoded_path, "resources", "package_1", "package.json")
    if os.path.exists(pkg_json):
        try:
            with open(pkg_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if data.get('package_name') == old_package:
                data['package_name'] = new_package
                with open(pkg_json, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                log("更新 package.json")
        except Exception as e:
            log(f"  更新 package.json 跳过: {e}")

    log("包名修改完成!")
    return True


def auto_detect_mode(decoded_path):
    """自动判断用含类还是不改类模式"""
    manifest = os.path.join(decoded_path, "AndroidManifest.xml")
    if not os.path.exists(manifest):
        return 'modify_pkg'

    with open(manifest, 'r', encoding='utf-8') as f:
        content = f.read()
    pkg_match = re.search(r'package="([^"]+)"', content)
    old_pkg = pkg_match.group(1) if pkg_match else ''

    # 检查是否有 .so（APKEditor 解压在 root/lib/）
    has_so = False
    for lib_candidate in ['root/lib', 'lib']:
        lib_dir = os.path.join(decoded_path, lib_candidate)
        if os.path.exists(lib_dir):
            for r, dirs, files in os.walk(lib_dir):
                if any(f.endswith('.so') for f in files):
                    has_so = True
                    break
        if has_so:
            break

    # 检查包名是否作为类前缀出现在 android:name 中
    pkg_as_prefix = False
    names = re.findall(r'android:name="([^"]+)"', content)
    for n in names:
        if n.startswith(old_pkg + '.'):
            pkg_as_prefix = True
            break

    if has_so:
        log("检测到 .so 动态库 → 使用仅改包名(不改类)模式")
        return 'pkg_only'

    if not pkg_as_prefix:
        log("包名未出现在类路径中 → 使用仅改包名(不改类)模式")
        return 'pkg_only'

    log("包名即类前缀，无 .so → 使用修改包名(含类)模式")
    return 'modify_pkg'


def mode_decompile(java_bin):
    apk_files = scan_apk_files()
    if not apk_files:
        print("错误: apk 目录下未找到 APK 文件")
        return

    items = [{'label': f"{a['filename']} ({a['size']:.1f} MB)", 'value': a} for a in apk_files]
    selected = choose_item(items, "请选择要反编译的 APK:")['value']

    base = selected['name_no_ext']
    out = os.path.join(DECODED_DIR, base)
    if os.path.exists(out):
        log("清理旧的解码目录...")
        shutil.rmtree(out)

    cmd = f'"{java_bin}" -Xmx4g -jar "{APKEDITOR_JAR}" d -i "{selected["filepath"]}" -o "{out}" -f'
    if run_cmd(cmd, "反编译 APK"):
        print(f"\n解码完成: decoded/{base}/")


def mode_modify_package():
    dirs = scan_decoded_dirs()
    if not dirs:
        print("错误: decoded 目录下未找到解码目录")
        print("请先执行反编译操作")
        return

    items = [{'label': d['name'], 'value': d} for d in dirs]
    selected = choose_item(items, "请选择要修改包名的目录:")['value']

    new_package = select_package()
    if not new_package:
        return

    print(f"\n{'=' * 50}")
    print(f"目录: {selected['name']}")
    print(f"目标包名: {new_package}")
    print('=' * 50)

    if modify_package(selected['path'], new_package):
        print(f"\n包名修改完成: {selected['name']}")
    else:
        print("\n包名修改失败")


def change_package_only(decoded_path, new_package):
    """仅修改包名，不改类路径（兼容有 native .so 硬编码 JNI 类路径的 app）"""
    log(f"开始仅改包名，目标: {new_package}")

    old_package = get_package_from_manifest(decoded_path)
    if not old_package:
        log("错误: 无法获取原包名")
        return False
    log(f"原包名: {old_package}")

    old_prefix = '.'.join(old_package.split('.')[:-1]) + '.'

    # 1. 修改 manifest 的 package 属性
    manifest_path = os.path.join(decoded_path, "AndroidManifest.xml")
    with open(manifest_path, 'r', encoding='utf-8') as f:
        content = f.read()
    content = content.replace(f'package="{old_package}"', f'package="{new_package}"')
    with open(manifest_path, 'w', encoding='utf-8') as f:
        f.write(content)
    log("AndroidManifest.xml package 已更新")

    # 2. 替换文件中的完整包名（不是类前缀）
    old_path = old_package.replace('.', '/')
    new_path = new_package.replace('.', '/')
    extensions = ('.smali', '.xml', '.json', '.prop', '.txt', '.conf', '.ini')
    file_args = []
    for root, dirs, files in os.walk(decoded_path):
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext not in extensions:
                continue
            filepath = os.path.join(root, filename)
            file_args.append((filepath, old_package, new_package, old_path, new_path))

    total_files = len(file_args)
    log(f"找到 {total_files} 个文件，多进程替换中...")
    processes = max(1, cpu_count() // 2) if cpu_count() else 4
    replaced_count = 0
    with Pool(processes) as pool:
        for i, result in enumerate(pool.imap_unordered(_replace_pkg_only_worker, file_args, chunksize=50)):
            replaced_count += result
            if (i + 1) % max(1, total_files // 20) == 0 or i + 1 == total_files:
                pct = (i + 1) * 100 // total_files
                bar = '#' * (pct // 5) + '.' * (20 - pct // 5)
                print(f"  [{bar}] {pct}% ({i+1}/{total_files})", flush=True)

    log(f"处理 {total_files} 个文件，替换 {replaced_count} 个文件")

    # 3. 更新 resources 配置
    public_xml = os.path.join(decoded_path, "resources", "package_1", "res", "values", "public.xml")
    if os.path.exists(public_xml):
        try:
            with open(public_xml, 'r', encoding='utf-8') as f:
                content = f.read()
            if old_package in content:
                content = content.replace(old_package, new_package)
                with open(public_xml, 'w', encoding='utf-8') as f:
                    f.write(content)
                log("更新 public.xml")
        except Exception as e:
            log(f"  更新 public.xml 跳过: {e}")

    pkg_json = os.path.join(decoded_path, "resources", "package_1", "package.json")
    if os.path.exists(pkg_json):
        try:
            with open(pkg_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if data.get('package_name') == old_package:
                data['package_name'] = new_package
                with open(pkg_json, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                log("更新 package.json")
        except Exception as e:
            log(f"  更新 package.json 跳过: {e}")

    log("包名修改完成! (类路径未改动)")
    return True


def mode_package_only():
    dirs = scan_decoded_dirs()
    if not dirs:
        print("错误: decoded 目录下未找到解码目录")
        return

    items = [{'label': d['name'], 'value': d} for d in dirs]
    selected = choose_item(items, "请选择要修改包名的目录:")['value']

    new_package = select_package()
    if not new_package:
        return

    print(f"\n目录: {selected['name']}")
    print(f"目标包名: {new_package}")
    print("(此模式仅改 Manifest 包名和完整包名字符串，不改类路径)")

    if change_package_only(selected['path'], new_package):
        print(f"\n包名修改完成: {selected['name']}")
    else:
        print("\n包名修改失败")


def mode_build(java_bin):
    dirs = scan_decoded_dirs()
    if not dirs:
        print("错误: decoded 目录下未找到解码目录")
        print("请先执行反编译操作")
        return

    items = [{'label': d['name'], 'value': d} for d in dirs]
    selected = choose_item(items, "请选择要编译的目录:")['value']

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output = os.path.join(OUTPUT_DIR, f"{selected['name']}_{timestamp}.apk")

    cmd = f'"{java_bin}" -Xmx4g -jar "{APKEDITOR_JAR}" b -i "{selected["path"]}" -o "{output}" -f'
    if not run_cmd(cmd, "编译 APK"):
        if os.path.exists(output):
            os.remove(output)
        return

    cmd = f'"{java_bin}" -jar "{UBER_APK_SIGNER}" --apks "{output}" --ks "{KEYSTORE}" --ksPass android --ksAlias androiddebugkey --ksKeyPass android --allowResign --overwrite'
    if not run_cmd(cmd, "签名 APK"):
        return

    print(f"\n完成！输出: {output}")


def mode_full_auto(java_bin):
    """全自动：反编译 → 修改包名(智能) → 编译签名"""
    # 1. 选 APK + 反编译
    apk_files = scan_apk_files()
    if not apk_files:
        print("错误: apk 目录下未找到 APK 文件")
        return

    items = [{'label': f"{a['filename']} ({a['size']:.1f} MB)", 'value': a} for a in apk_files]
    selected = choose_item(items, "请选择要处理的 APK:")['value']

    base = selected['name_no_ext']
    out = os.path.join(DECODED_DIR, base)
    if os.path.exists(out):
        print(f"清理旧解码目录: {base}")
        shutil.rmtree(out)

    cmd = f'"{java_bin}" -Xmx4g -jar "{APKEDITOR_JAR}" d -i "{selected["filepath"]}" -o "{out}" -f'
    if not run_cmd(cmd, "反编译 APK"):
        return
    print(f"解码完成: decoded/{base}/\n")

    # 2. 选包名 + 智能修改
    new_package = select_package()
    if not new_package:
        return

    mode = auto_detect_mode(out)
    log(f"智能选择结果: {'修改包名(含类)' if mode == 'modify_pkg' else '仅改包名(不改类)'}")

    if mode == 'pkg_only':
        print("\n" + "!" * 50)
        print("! 该应用包含 .so 动态库，只能使用「仅改包名(不改类)」模式。")
        print("! 类路径将保持不变，只修改 Manifest 包名和完整包名字符串。")
        print("!" * 50)
        try:
            choice = input("\n是否继续? (y/N): ").strip().lower()
        except KeyboardInterrupt:
            return
        if choice != 'y':
            print("已取消")
            return

    if mode == 'modify_pkg':
        if not modify_package(out, new_package):
            print("\n包名修改失败")
            return
        print(f"\n包名修改完成 (含类)\n")
    else:
        if not change_package_only(out, new_package):
            print("\n包名修改失败")
            return
        print(f"\n包名修改完成 (不改类)\n")

    # 3. 编译签名
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output = os.path.join(OUTPUT_DIR, f"{base}_{timestamp}.apk")
    cmd = f'"{java_bin}" -Xmx4g -jar "{APKEDITOR_JAR}" b -i "{out}" -o "{output}" -f'
    if not run_cmd(cmd, "编译 APK"):
        if os.path.exists(output):
            os.remove(output)
        return
    cmd = f'"{java_bin}" -jar "{UBER_APK_SIGNER}" --apks "{output}" --ks "{KEYSTORE}" --ksPass android --ksAlias androiddebugkey --ksKeyPass android --allowResign --overwrite'
    if not run_cmd(cmd, "签名 APK"):
        return
    print(f"\n全自动完成！输出: {output}")
    print(f"解码目录保留: decoded/{base}/")


def mode_auto():
    dirs = scan_decoded_dirs()
    if not dirs:
        print("错误: decoded 目录下未找到解码目录")
        return

    items = [{'label': d['name'], 'value': d} for d in dirs]
    selected = choose_item(items, "请选择要修改包名的目录:")['value']

    new_package = select_package()
    if not new_package:
        return

    mode = auto_detect_mode(selected['path'])
    log(f"智能选择结果: {'修改包名(含类)' if mode == 'modify_pkg' else '仅改包名(不改类)'}")

    if mode == 'pkg_only':
        print("\n" + "!" * 50)
        print("! 该应用包含 .so 动态库，只能使用「仅改包名(不改类)」模式。")
        print("! 类路径将保持不变，只修改 Manifest 包名和完整包名字符串。")
        print("!" * 50)
        try:
            choice = input("\n是否继续? (y/N): ").strip().lower()
        except KeyboardInterrupt:
            return
        if choice != 'y':
            print("已取消")
            return

    if mode == 'modify_pkg':
        if modify_package(selected['path'], new_package):
            print(f"\n包名修改完成 (含类): {selected['name']}")
        else:
            print("\n包名修改失败")
    else:
        if change_package_only(selected['path'], new_package):
            print(f"\n包名修改完成 (不改类): {selected['name']}")
        else:
            print("\n包名修改失败")


def main():
    java_bin = find_java()
    if not check_environment(java_bin):
        input("按回车键退出...")
        sys.exit(1)

    while True:
        items = [
            {'label': '全自动 — 反编译 → 修改包名(智能) → 编译签名', 'value': 'full_auto'},
            {'label': '反编译 — 将 APK 解码到 decoded/ 目录', 'value': 'decompile'},
            {'label': '修改包名 — 智能选择含类/不改类', 'value': 'auto'},
            {'label': '编译 — 从 decoded/ 目录编译签名 APK', 'value': 'build'},
            {'label': '退出', 'value': 'exit'},
        ]
        choice = choose_item(items, "请选择操作模式:")

        if choice['value'] == 'exit':
            print("再见!")
            break
        elif choice['value'] == 'full_auto':
            mode_full_auto(java_bin)
        elif choice['value'] == 'decompile':
            mode_decompile(java_bin)
        elif choice['value'] == 'auto':
            mode_auto()
        else:
            mode_build(java_bin)


if __name__ == '__main__':
    freeze_support()
    try:
        main()
    except KeyboardInterrupt:
        print("\n用户取消")
    except Exception as e:
        log(f"执行出错: {e}")
        input("按回车键退出...")
