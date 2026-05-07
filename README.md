# APK 包名替换工具

一键apk反编译、包名替换、打包、签名工具。

将 APK 的包名替换为其他包名，适用于车机等设备对特定包名有验证的场景。

---

## 环境要求

- **Java**: JDK 17+
- **Python**: 3.8+

---

## 使用方法

### 第一步：放入 APK

将待处理的 APK 文件放入 `apk/` 目录（支持多个 APK 文件）。

### 第二步：运行脚本

双击运行或执行：

```bash
python repackage_apk.py
```

### 第三步：选择 APK

脚本会自动扫描 `apk/` 目录，显示所有 APK 文件供选择。

### 第四步：选择目标包名

从 `name.txt` 中的预置包名列表选择，或直接回车使用第一个。

### 第五步：等待完成

脚本会自动完成：
1. 反编译 APK
2. 替换包名（包括 smali、xml、resources 等所有位置）
3. 重新打包
4. 签名

输出 APK 位于 `apk/` 目录，文件名格式：`原包名_时间戳.apk`

---

## 配置文件

### name.txt - 包名列表

在 `name.txt` 中配置可用的目标包名：

```txt
#斗鱼
air.tv.douyu.android
#快手
com.smile.gifmaker
#优酷
com.youku.phone
#斗地主
com.qqgame.hlddz
```

格式说明：
- `#` 开头的行表示注释/描述
- 空白行会被忽略

---

## 目录结构

```
apk_editer/
├── README.md                    # 本说明文档
├── repackage_apk.py             # 主程序 (双击运行)
├── name.txt                    # 目标包名配置
├── apk/                        # APK文件目录
│   ├── xxx.apk                 # 放入待处理的APK
│   └── 原包名_时间戳.apk       # 输出的签名APK
├── log/                        # 日志目录
└── libs/                       # 工具库
    ├── APKEditor.jar           # APK编辑器
    ├── uber-apk-signer.jar     # APK签名工具
    ├── debug.keystore          # 签名密钥
    ├── fix_package.py          # 批量替换脚本 (备用)
    └── view_apk_info.py        # 查看APK信息 (备用)
```

---

## 常见问题

### 1. 安装后闪退

可能原因：
- 包名替换不完整
- 应用有包名校验

解决：确保目标包名正确，或尝试其他包名。

### 2. 提示 "签名不一致"

先 **卸载手机上已安装的同名应用**，再安装新的 APK。

### 3. apk 目录下没有 APK 文件

确保将 APK 文件放入 `apk/` 目录后重新运行脚本。

---

## 注意事项

1. 替换包名后，应用数据会重置
2. 部分应用有包名校验，替换后可能无法运行
3. 仅供学习和测试使用

---
