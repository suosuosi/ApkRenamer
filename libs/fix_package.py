"""
APK包名批量替换脚本

使用说明:
    python fix_package.py <反编译目录> <旧包名> <新包名>

示例:
    python fix_package.py jellyfin_decoded org.jellyfin.mobile air.tv.douyu.android
"""

import os
import sys

def replace_in_file(filepath, old_str, new_str):
    """替换文件中的字符串"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if old_str in content:
            content = content.replace(old_str, new_str)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        return False
    except Exception as e:
        print(f"处理文件出错: {filepath}, 错误: {e}")
        return False

def process_directory(base_dir, old_package, new_package):
    """处理目录下所有smali文件和XML文件"""
    # 转换包名为路径格式: org.jellyfin.mobile -> org/jellyfin/mobile/
    old_path = old_package.replace('.', '/') + '/'
    new_path = new_package.replace('.', '/') + '/'
    
    count = 0
    processed_extensions = ['.smali', '.xml']
    
    print(f"正在处理目录: {base_dir}")
    print(f"旧包名路径: {old_path}")
    print(f"新包名路径: {new_path}")
    
    for root, dirs, files in os.walk(base_dir):
        for filename in files:
            ext = os.path.splitext(filename)[1]
            if ext in processed_extensions:
                filepath = os.path.join(root, filename)
                if replace_in_file(filepath, old_path, new_path):
                    count += 1
                    if count % 100 == 0:
                        print(f"已处理 {count} 个文件...")
    
    print(f"总计修改文件数: {count}")
    return count

def main():
    if len(sys.argv) != 4:
        print("用法: python fix_package.py <反编译目录> <旧包名> <新包名>")
        print("示例: python fix_package.py jellyfin_decoded org.jellyfin.mobile air.tv.douyu.android")
        sys.exit(1)
    
    base_dir = sys.argv[1]
    old_package = sys.argv[2]
    new_package = sys.argv[3]
    
    if not os.path.exists(base_dir):
        print(f"错误: 目录不存在: {base_dir}")
        sys.exit(1)
    
    process_directory(base_dir, old_package, new_package)
    print("\n完成!")

if __name__ == '__main__':
    main()