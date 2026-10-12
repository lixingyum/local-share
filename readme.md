# Local Share 共享暂存板

一个轻量级的局域网共享工具：在同一热点/局域网内，手机、平板、电脑可以互传文本、图片和文件，实时同步，无需安装 App，打开浏览器即可使用。

---

## 功能特性

- 📝 **文本、图片、文件** 一键上传与下载
- 📋 **粘贴自动发送**：复制后直接在输入框 Ctrl+V，自动上传
- ⚡ **实时同步**：基于 WebSocket，所有设备秒级更新
- 🔍 **分类筛选**：全部 / 文本 / 图片 / 文件
- ⏱ **时间窗口**：普通设备仅显示最近 10 分钟内容
- 👑 **管理员模式**：启动服务的本机自动成为管理员，可查看全部历史、重新发送、删除文件
- 🔒 **无损传输**：文件二进制原样保存，不压缩不转码
- 🌐 **离线可用**：不依赖公网，热点内即可工作

---

## 环境要求

- Python 3.7 及以上
- 依赖库：`flask`、`flask-socketio`
- 一台设备作为服务器（手机或电脑）
- 其他设备通过浏览器访问

---

## 目录结构

```
local-share/
├── server.py                # 主程序
├── static/
│   └── socket.io.min.js     # Socket.IO 客户端库（离线必需）
├── shared_files/            # 上传的文件存储目录（自动创建）
└── metadata.json            # 文件元数据（自动创建）
```

---

## 快速开始（电脑端）

### 1. 安装依赖

```bash
pip install flask flask-socketio
```

### 2. 准备 socket.io 客户端库（离线必需）

在有网络的电脑上下载：

```
https://cdn.socket.io/4.5.4/socket.io.min.js
```

保存到项目目录下的 `static/` 文件夹中（如没有则新建）：

```
项目根目录/
├── server.py
└── static/
    └── socket.io.min.js
```

确认 `server.py` 中的 HTML 模板引用的是本地路径：

```html
<script src="/static/socket.io.min.js"></script>
```

> 如果必须使用 CDN，可以改为 `https://cdn.socket.io/4.5.4/socket.io.min.js`，但**热点无公网时页面将无法工作**。

### 3. 启动服务

```bash
python server.py
```

启动后终端会打印本机管理 IP 集合和监听地址：

```
本机管理 IP 集合: {'127.0.0.1', '192.168.1.100', '::1'}
启动服务...
 * Running on http://192.168.1.100:4001
```

### 4. 访问

- 服务器本机浏览器打开 `http://localhost:4001` 或 `http://本机IP:4001` → **管理端**
- 其他设备打开 `http://服务器IP:4001` → **普通共享端**

---

## 在手机上启动服务（Termux）

Android 手机可以通过 Termux 运行 Python 服务，把手机变成一个便携的共享服务器。

### 1. 安装 Termux

从以下渠道下载安装（**不要用 Google Play 版本，已停更**）：

- F-Droid：`https://f-droid.org/packages/com.termux/`
- GitHub Releases：`https://github.com/termux/termux-app/releases`

### 2. 初始化并安装依赖

打开 Termux，依次执行：

```bash
pkg update && pkg upgrade
pkg install python
pip install flask flask-socketio
```

### 3. 准备项目文件

推荐直接放在 Termux 的内部存储中运行。如果项目放在外接硬盘或手机存储上，需要复制到 `$HOME` 目录：

```bash
mkdir -p ~/local-share
cp -r /路径/到/local-share/* ~/local-share/
cd ~/local-share
```

或者直接在 Termux 中用 `nano server.py` 粘贴完整代码。

同时确认 `static/socket.io.min.js` 已就位：

```bash
mkdir -p static
# 将下载好的 socket.io.min.js 放入 static/ 目录
```

### 4. 启动服务（推荐无缓冲模式）

```bash
python -u server.py
```

`-u` 参数让 Python 使用无缓冲 stdout，确保日志即时显示，不会等到退出才输出。

看到类似输出即成功：

```
本机管理 IP 集合: {'127.0.0.1', '172.20.10.4', '::1'}
启动服务...
 * Running on http://172.20.10.4:4001
```

### 5. 让其他设备访问

- 确保手机已开启**个人热点**，其他设备连接该热点。
- 记下 Termux 中显示的局域网 IP（如 `172.20.10.4`）。
- 其他设备浏览器打开：`http://172.20.10.4:4001`
- 手机本机浏览器打开同一地址，会自动识别为**管理端**。

### 6. 保持后台运行

**临时后台运行：**

```bash
nohup python -u server.py > /dev/null 2>&1 &
```

关闭 Termux 窗口后服务继续运行。

**防止被系统杀死：**

- 手机设置 → 应用 → Termux → 电池 → 选择「无限制」
- 在 Termux 中获取唤醒锁：
  ```bash
  pkg install termux-api
  termux-wake-lock
  ```

**开机自启（需安装 Termux:Boot）：**

1. 安装 Termux:Boot（F-Droid 或 GitHub）。
2. 创建启动脚本：
   ```bash
   mkdir -p ~/.termux/boot
   nano ~/.termux/boot/start-share.sh
   ```
   
   内容：
   ```bash
   #!/data/data/com.termux/files/usr/bin/sh
   termux-wake-lock
   cd ~/local-share
   nohup python -u server.py > /dev/null 2>&1 &
   ```
3. 赋予执行权限：
   ```bash
   chmod +x ~/.termux/boot/start-share.sh
   ```
4. 重启手机后服务会自动启动。

### 7. 热点设置注意事项

- 部分手机热点默认开启 **AP 隔离**，会导致设备之间无法互访，需在热点设置中关闭「客户端隔离」或开启「允许设备互访」。
- 关闭「无设备时自动关闭热点」选项，避免服务中断。

---

## 从外接固态硬盘/手机存储启动项目

由于 Android 对外部存储（如 USB 固态硬盘）默认使用 `noexec`（禁止执行）选项挂载，**无法直接从外接存储运行 `server.py`**，必须先复制到 Termux 内部存储。

### 操作步骤

1. **确认硬盘挂载路径**
   
   ```bash
   ls /mnt/media_rw/
   ```
   
   通常会看到类似 `1ED5-6B3B` 的目录名（硬盘序列号）。
2. **复制项目到内部存储**
   
   ```bash
   mkdir -p ~/local-share
   cp -r /mnt/media_rw/1ED5-6B3B/local-share/* ~/local-share/
   cd ~/local-share
   ```
3. **启动服务**
   
   ```bash
   python -u server.py
   ```

### 一键同步并启动脚本

在 `~/start-share.sh` 中写入：

```bash
#!/data/data/com.termux/files/usr/bin/bash
DRIVE="/mnt/media_rw/1ED5-6B3B/local-share"

if [ ! -d "$DRIVE" ]; then
    echo "未检测到硬盘或项目目录"
    exit 1
fi

mkdir -p ~/local-share
cp -r "$DRIVE"/* ~/local-share/
cd ~/local-share
python -u server.py
```

赋予执行权限：

```bash
chmod +x ~/start-share.sh
```

之后每次插上硬盘，只需运行 `~/start-share.sh` 即可。

> 💡 **进阶用法**：可以将 `server.py` 中的 `UPLOAD_FOLDER` 指向硬盘路径（如 `/mnt/media_rw/1ED5-6B3B/shared_files`），把上传的文件直接保存到硬盘，节省手机内部空间。但**代码本身必须放在内部存储运行**。

---

## 管理员说明

- **只有启动服务的本机**（通过 `127.0.0.1` 或本机局域网 IP 访问）会被识别为管理员。
- IP 识别采用**跨平台多级降级策略**，兼容 Windows、macOS、Linux 和 Termux：
  1. `hostname -I`
  2. `ip addr`
  3. **UDP 连接法**（向 8.8.8.8 探测出站 IP，不实际发包，无需公网）
  4. `socket.gethostbyname_ex` 兜底
- 管理员默认也只看到最近 10 分钟内容，但可以通过「📂 显示全部文件」按钮查看所有历史。
- 在“显示全部”模式下，每条内容右侧会出现：
  - **🔄 重新发送**：将该条目时间戳更新为当前时间，使其重新出现在普通设备的 10 分钟窗口中，**不会产生重复文件**。
  - **🗑️ 删除**：永久删除服务器上的文件和记录。
- 其他设备无法看到这些管理按钮。

---

## 常见问题

**Q：手机上启动服务后，日志延迟到退出才显示？**
A：这是 Termux 下 Python stdout 块缓冲导致的。用 `python -u server.py` 启动即可，或在代码顶部加入：

```python
import sys
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)
```

**Q：手机上看到“本机管理 IP 集合”打印了两次？**
A：这是 `debug=True` 时 Flask reloader 启动了主进程和子进程各执行一次。在手机上应使用 `debug=False` 启动：

```python
socketio.run(app, host='0.0.0.0', port=4001, debug=False, allow_unsafe_werkzeug=True)
```

**Q：页面点击没反应，按钮无效？**
A：检查 `static/socket.io.min.js` 是否已放置，以及 HTML 中是否已改为本地引用。按 F12 打开控制台，若提示 `io is not defined` 即是此问题。

**Q：其他设备无法访问？**
A：

- 确认访问地址为 `http://服务器IP:4001`，不要漏掉端口。
- 检查手机热点是否开启了 AP 隔离。
- 检查电脑防火墙是否允许 4001 端口入站。
- 在电脑上 `ping 服务器IP` 测试连通性。

**Q：手机 Termux 中 IP 检测不到？**
A：代码已内置 UDP 连接法，通常可自动获取。即使热点没有接入公网，UDP 连接法仍有效（它只查路由表，不发包）。

**Q：服务端报 `sethostname: ...` 错误？**
A：这是 Windows 下执行 `hostname -I` 的正常报错，已被 try/except 捕获，不影响功能。可忽略。

**Q：如何停止服务？**
A：在运行服务的终端按 `Ctrl+C`。若使用 `nohup` 后台运行，可用 `ps aux | grep server.py` 找到进程号后 `kill`。

---

## 安全提示

- 本工具设计为**局域网内部使用**，请勿将端口暴露到公网。
- 管理员权限基于 IP 识别，仅限服务器本机，相对安全。
- 上传的文件保存在服务器 `shared_files/` 目录中，请定期清理。

---

## 许可证

MIT License，自由使用与修改。

