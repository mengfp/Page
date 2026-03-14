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

  可从 [age releases](https://github.com/FiloSottile/age/releases) 下载 Windows 包，把上述两个 exe 放到与主程序同一目录：
  - **源码运行**：项目根目录（与 `crypto.py` 同级）  
  - **发布**：整包为一个文件夹——`Page.exe` + `age.exe` + `age-plugin-batchpass.exe` + 依赖（**不单文件 exe**，避免每次启动解压、也方便 age 子进程）

## 安装（开发）

```bash
pip install -r requirements.txt
```

## 运行

```bash
python main.py
python main.py C:\path\to\notes.page
```

第二行：命令行传入一个 `.page` 路径时，启动后会提示口令并打开该文件（与将来「双击关联到 **Page.exe**」行为一致；开发时用 `python main.py <路径>` 即可试）。

启动时会检查 **age.exe** 与 **age-plugin-batchpass.exe** 是否在预期目录；缺失则提示路径并退出。

## 测试（可选）

```bash
python -m unittest discover -s tests -p "test_*.py"
```

仅依赖标准库 + `store`（无需启动 GUI）。

版本号在 **`version.py`**（发布前改 `__version__`）；菜单 **Help → About Page** 可查看。

## 分发建议

**只考虑文件夹分发**：主程序 + 两个 age 的 exe 同目录（PyInstaller 用 **onedir**，勿用 onefile）。不单 exe，省去解压与路径折腾。

## 生成 Page.exe（PyInstaller onedir）

1. 项目根目录已放好 **`age.exe`**、**`age-plugin-batchpass.exe`**；图标在 **`ui/page.ico`**（可选 **`ui/password.ico`** 供打开文件口令框）。  
2. 安装打包工具：`pip install pyinstaller`  
3. 在项目根执行：

```bash
pyinstaller Page.spec
```

4. 结果目录：**`dist/Page/`**  
   - 运行 **`Page.exe`**（同目录下 `_internal` 内已含 Python、PySide6 及两个 age；`crypto` 在 frozen 下用 `_MEIPASS`，无需手抄 dll）。  
5. **分发**：把 **`dist/Page` 整个文件夹** 拷走即可（勿只拷单个 exe）。  
6. 关联 `.page` 时，注册表里命令行指向 **`...\Page\Page.exe" "%1"`**。

打包体积：`Page.spec` 里已排除未使用的 Qt 模块（QML/WebEngine/多媒体等），一般比默认 PyInstaller 瘦一截。若启动报错，从 `excludes` 里删掉相关模块再打包。本机若安装 [UPX](https://github.com/upx/upx)，`upx=True` 还可再压一点 DLL。

窗口图标：`EXE(icon=ui/page.ico)` 只影响资源管理器里 exe 的图标；**运行后标题栏/任务栏** 靠 `setWindowIcon` 加载 **`page.ico`**（`datas` 打进 `_MEIPASS`）。**`ui/password.ico`** 可选，供 **打开文件 / 新建与 Save As 设口令** 两个对话框；存在时 `Page.spec` 会一并打包。

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
