# ApkRenamer -- APK 包名替换工具

将 APK 的包名替换为其他包名，适用于车机等设备对特定包名有验证的场景。

## 环境要求

- **Java**: JDK 17+
- **Python**: 3.8+

## 快速开始

```bash
python build_apk.py
```

程序提供交互式菜单，按步骤操作即可。

## 功能模式

### 1. 全自动模式 (推荐)
一键完成：反编译 → 智能修改包名 → 编译签名。自动检测是否包含 `.so` 动态库，智能选择改包名方式。

### 2. 反编译
将 `apk/` 目录下的 APK 解包到 `decoded/` 目录，使用 [APKEditor](https://github.com/REAndroid/APKEditor) 解码。

### 3. 修改包名（智能）
基于检测结果**自动选择**两种模式：
- **包名+类路径模式**：修改 manifest 包名 + 替换所有文件中的包名引用 + 重命名 smali 目录结构
- **仅包名模式**：只修改 manifest 包名和完整包名字符串，保留类路径不动（适用于含 `.so` 的应用，避免 JNI 硬编码类名路径炸裂）

### 4. 编译签名
将 `decoded/` 下的解码目录重新打包为 APK 并签名，输出到 `output/` 目录（带时间戳）。

## 智能检测逻辑

`auto_detect_mode()` 自动判断改包名策略：
1. 扫描 `lib/` 目录是否有 `.so` 文件 → 有则走 `pkg_only`（不改类）
2. 检查 `android:name` 是否以包名开头 → 否则走 `pkg_only`
3. 两者都满足 → 走 `modify_pkg`（含类）

类路径前缀检测 `detect_class_prefix()` 支持三级策略：
1. 优先匹配包名下的类
2. 匹配同前两段的类（过滤 alipay、tencent 等第三方）
3. 回退使用包名本身

## 配置文件

### name.txt — 包名列表

```txt
#斗鱼
air.tv.douyu.android
#快手
com.smile.gifmaker
```

- `#` 开头的行表示描述
- 非空行即为目标包名

## 目录结构

```
apkRenamer2/
├── build_apk.py                 # 主程序（交互式菜单）
├── repackage_apk_by_step.py     # 分步执行脚本（每步确认）
├── name.txt                     # 目标包名配置
├── apk/                         # 放入待处理的 APK 文件
├── decoded/                     # 反编译后的解码目录
├── output/                      # 编译输出的签名 APK（带时间戳）
├── log/                         # 分步脚本的运行日志
├── libs/
│   ├── APKEditor.jar            # APK 解包/打包工具
│   ├── uber-apk-signer.jar      # APK 签名工具
│   ├── debug.keystore           # 调试签名密钥（自动生成）
│   ├── fix_package.py           # 命令行批量替换脚本（备用）
│   └── view_apk_info.py         # APK 信息查看工具（备用）

```

## 常见问题

### 安装后闪退
- 包名替换不完整，或应用存在包名校验
- 如果原 APK 含 `.so` 动态库，确保走的是「仅改包名」模式

### 签名不一致
先卸载手机上旧应用再安装新 APK

### 支持哪些 APK
支持没有加固/壳的普通 APK。加壳 APK 解码后 smali 文件过少，程序会给出警告
