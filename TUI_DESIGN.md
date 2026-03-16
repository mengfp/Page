# Page — TUI 设计（page.py / curses）

> 目标：在终端（Linux / Termux / SSH）下提供一个**轻量、可靠的应急视图**，  
> 逻辑与 GUI 版共用 `store.py` 的数据与搜索行为，只换一套 UI。

---

## 1. 目标与范围

- **主要场景**：Termux + SSH 终端（手机 / 服务器）。不在 Linux 上跑 GUI。
- **平台**：优先 Linux / Termux；在 Windows 上如需使用，依赖 `windows-curses` 或 WSL。
- **职责**：
  - 一次解密 `.page` 文件并常驻内存。
  - 提供**只读浏览**：搜索 + 列表 + 详情。
  - 键位与布局适合小终端和软键盘。
- **不做（当前版本）**：
  - 不编辑、不 Apply、不 Save/Save As。
  - 不新建/删除条目。
  - 不按 tag 显式过滤（靠搜索 + tag 参与全文检索）。
- **约束**：不修改现有公共代码（`store.py` / `app.py` / `crypto.py` / `main_window.py` / `ui/*`）。TUI 自己解决解密与显示。

---

## 2. 数据与解密

- `.page` 磁盘格式与 GUI 完全一致（见 `DESIGN.md` §2.1 和 `store.py`）：
  - 解密后为 UTF-8 JSON：根字段 `id` / `version` / `entries`。
  - 每条 entry：`title` / `tags[]` / `content` / `modified`（ISO 8601）。
  - `Store.from_bytes(raw)` / `store.to_bytes()` 与 GUI 共用。
- `store.search(keyword)` 行为与 GUI 相同：
  - 按空格分词为多个词。
  - 多词 AND：每个词都需在标题 / 标签 / 正文任一字段中出现。
  - 区分度通过字符串子串匹配（不区分大小写）。

### 2.1 解密（只在 TUI 内）

- 假定系统已安装 **`age`**，且可用：

  ```bash
  age --version
  ```

- TUI 不使用项目内的 `crypto.py` / `age-plugin-batchpass`，而是直接子进程调用：

  ```bash
  age -d /path/to/file.page
  ```

  - `stdin=None`：让 `age` 自行在终端里询问 passphrase。
  - 捕获 `stdout` 作为明文字节；若 `returncode != 0`，将 `stderr` 显示给用户并退出。
- 解密成功后：调用

  ```python
  store = Store.from_bytes(plaintext_bytes)
  ```

  将文档载入内存，此后整个 TUI 会话只使用这一份 `Store`，**不会再询问 passphrase**。

---

## 3. 总体交互流程

入口命令：

```bash
python page.py /path/to/notes.page
```

1. 参数检查：需要一个 `.page` 路径，否则打印 usage 并退出。
2. 调用 `age -d` 一次，age 在终端提示 passphrase；解密失败时退出。
3. 使用 `Store.from_bytes` 构造 `Store` 实例。
4. 进入 curses 主循环：
   - 初始视图是 **列表视图**（含搜索框）。
   - 用户可以：
     - 在搜索框中输入关键字实时筛选。
     - 用方向键在结果中移动。
     - Enter 打开条目详情。
     - 在详情视图中滚动正文，按 ESC 返回列表。
     - 在列表视图按 ESC 退出程序（字母键如 q 仅作为搜索输入，不做控制）。

当前版本不支持修改 store 的内容；后续若增加编辑/保存，将在本文件中补充规则。

---

## 4. 布局与视图

TUI 只有两种主要视图：**列表视图** 和 **详情视图**。根据终端大小可做简单适配，但总体结构不变。

### 4.1 列表视图

布局（从上到下）：

1. **条目列表区域（若干行，可滚动）**
   - 每行显示一个 entry 的摘要：
     - `索引`（右对齐，3 宽）+ 空格
     - `title`（截断以适应屏宽，空则显示 `(untitled)`）
     - 空格 + `modified`（`YYYY-MM-DD HH:MM`）
   - 使用独立的 `displayed` 列表存放当前搜索结果；不会改变 `store.entries`。
   - 当前选中行以反色高亮；条目多于屏高时列表窗口滚动，保持选中行可见。

2. **搜索框（最后 1 行）**
   - 文案：`Search: `，后接当前搜索字符串。
   - 置于底部，靠近软键盘，减少视线上下跳动。
   - 焦点常驻搜索框：用户直接键入字符即修改搜索词。
   - 行为：
     - 每次输入/删除字符后，立即调用 `store.search(search_text)`，更新 `displayed` 列表。
     - 无搜索词（空字符串）表示显示全部条目。

无底部状态行；键位仅用方向键、Enter、ESC、Backspace 与可打印字符。

### 4.2 列表视图键位

- **光标移动**（仅方向键，字母键不参与控制）：
  - `UP`：向上移动选中行。
  - `DOWN`：向下移动选中行。
- **打开详情**：
  - `Enter`：打开当前选中条目（若结果非空）。
- **退出**：
  - `ESC`：退出整个 TUI。（`q` 等字母仅作为搜索输入，输入 "bbq" 不会误退出。）
- **搜索框编辑**：
  - 可打印 ASCII 字符（`32–126`）：追加到搜索字符串。
  - `Backspace`（`KEY_BACKSPACE` / 127 / 8）：删除最后一个字符。
  - 搜索字符串变化后，立刻 `displayed = store.search(search_text)` 并重置/裁剪选中索引，避免越界。

> 说明：暂不实现标签过滤；`tags` 已参与 `Entry.matches`，因此搜索关键字中包含 tag 文本即可筛到相关条目。

### 4.3 详情视图

布局：

1. **头部信息（多行）**
   - `Title: <title or (untitled)>`
   - `Date : <modified in local time zone, YYYY-MM-DD HH:MM:SS>`
   - `Tags : <comma-separated tags or "—">`
   - 一行分隔线：`-` × 屏宽。

2. **正文区域（多行，可滚动）**
   - 来自 `entry.content.splitlines()`，空内容时显示单个空行。
   - 根据窗口高度与当前滚动偏移 `_scroll` 截取可见部分绘制。

无底部状态行。

键位（仅方向与功能键，字母键不参与控制）：

- `UP`：向上滚动一行。
- `DOWN`：向下滚动一行。
- `PageUp`：向上滚动若干行（如 10 行）。
- `PageDown`：向下滚动若干行。
- `ESC`：返回列表视图。

---

## 5. 小终端 / Termux 优化

- TUI 使用 `stdscr.getmaxyx()` 确定终端大小。
- 目标是 **在 ~80×24 以及小于此尺寸的终端上仍能正常使用**：
  - 顶部搜索框始终保留一行。
  - 列表区域高度 = `max_y - 2` 行（中间高度），确保至少能看见若干条。
  - 标题做截断，确保每行不会因为过多信息而换行。
  - 详情视图将正文滚动显示，不强求在一屏内展示完整笔记。
- 键位全部为简单键，且**字母键不做控制符**（避免搜索 "bbq" 误触退出）：
  - 方向键 / `Enter` / `ESC` / `Backspace` / `PageUp` / `PageDown`，适合手机软键盘。

> 后续如需支持「窄屏单视图模式」（只列表或只详情）或更复杂布局，可在此基础上扩展。

---

## 6. 与 GUI / 公共代码的关系

- **共用**：
  - `Store` / `Entry` 定义与验证逻辑。
  - `.page` JSON 结构与版本号写入方式。
  - `Store.search()` 的全文搜索语义（多词 AND，字段：标题+标签+正文）。
- **TUI 自己负责**：
  - 解密（`age -d`，不使用 `crypto.py`）。
  - curses 界面、键位、滚动与重绘。
  - 错误提示（age 解密失败、JSON 不合法等）。
- **不修改**：
  - `store.py` / `app.py` / `crypto.py` / Qt GUI 等现有模块。
  - 若 TUI 将来需要编辑/保存，也尽量通过 `Store` / `Entry` 公共接口实现，而不直接改这些模块的行为。

---

## 7. 后续可能的扩展（暂不实现）

仅列出方向，非需求：

- **编辑与保存**：
  - 在详情视图进入编辑模式，修改 title/tags/content。
  - 使用 `Store` 的新增/更新行为，与 GUI 的 Apply 语义对齐。
  - 保存时调用 `store.to_bytes()` 并通过 `age -e` 写回原文件（仍不修改公共 `crypto.py`）。
- **标签过滤 UI**：
  - 增加标签列表视图或弹出式 tag 选择器。
  - 当前过滤 = `store.search` 结果再按 tag 过滤，与 GUI 的 Filters 对齐。
- **多文件浏览**：
  - 支持在同一 TUI 会话中切换 `.page` 文件。

这些扩展实现前，应在本文件中先补充设计，再做代码更改。

