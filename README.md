# Page

Windows 下的本地加密笔记：数据用口令加密，只保存在本机 `.page` 文件中。

**交互与状态机（可随讨论改）见 [DESIGN.md](DESIGN.md)。**

## 功能

- 笔记存成 age 口令加密的 JSON（UTF-8，不压缩）
- 每条笔记：标题、标签（小 **chip**；**Tags 右侧 Add**；**右键 chip → Delete**）、正文
- 关键词搜索、按标签筛选；左侧笔记列表 **Title | Date | Tags**（Tags 逗号分隔，悬停看全文）
- 无账号、无云、无联网逻辑（除非你自己拷贝文件）

## 环境（仅 Windows）

- **Python 3.11+**（开发/直接运行源码时）
- **age（Windows）**  
  必须与程序能加载到的目录放在一起，且文件名固定为：
  - `age.exe`
  - `age-plugin-batchpass.exe`  

  可从 [age releases](https://github.com/FiloSottile/age/releases) 下载 Windows 包，把上述两个 exe 放到：
  - **源码运行**：与本项目里 `crypto.py` 同一目录（项目根目录），或  
  - **PyInstaller 单文件**：打进 bundle 后由 `sys._MEIPASS` 查找（需把两个 exe 一并打进资源）  
  - **发布文件夹**：整个文件夹里包含 `Page.exe`（或 `python main.py` 的启动方式）+ 两个 age 的 exe + 依赖，**两个 age 的 exe 必须与主程序/脚本同目录**（与当前 `crypto.py` 逻辑一致）

## 安装（开发）

```bash
pip install -r requirements.txt
```

## 运行

```bash
python main.py
```

版本号在 **`version.py`**（发布前改 `__version__`）；菜单 **Help → About Page** 可查看。

## 分发建议

- **单 exe**：用 PyInstaller 等打包时，把 `age.exe` 和 `age-plugin-batchpass.exe` 加入数据文件，并保证运行时的 `_MEIPASS` 里能访问到（与 `crypto._age_dir()` 一致）。  
- **文件夹分发**：用户解压后目录内包含主程序 + 两个 age 的 exe，无需单独配置 PATH（程序会把该目录插入 PATH 供 age 找插件）。

## 使用说明

- **File → New**：新建未保存文档  
- **File → Open**：打开 `.page`（需口令，不允许空口令）  
- **File → Save / Save As**：先把当前编辑 Apply 进内存，再加密写 `.page`（无单独只写盘）  
- **右侧 New**：新空白草稿（**Apply** 后才进列表）；**列表右键 → Delete**（或选中后 **Delete**）  
- 编辑后点 **Apply** 写入当前条目；**Cancel** 放弃本次修改  

## 文件格式

解密后为 UTF-8 JSON 数组；每条为对象：`title`、`tags`、`content`、`modified`（ISO 8601）。整段 JSON 由 age（batchpass 插件）加密，扩展名 `.page`。

## 许可证

All rights reserved.
