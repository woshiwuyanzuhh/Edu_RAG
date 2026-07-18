# MySQL 8.4 故障记录与快速排查手册

> 本机环境：Windows 10 | MySQL 8.4.9 | 安装路径 `F:\MySQL\MySQL Server 8.4\`
> 最后更新：2026-07-10

---

## 一、本次故障记录（2026-07-10）

### 故障现象

| 项目 | 状态 |
|------|------|
| `sc query MySQL84` | STOPPED |
| 端口 3306 | 被 PID 4080 占用（旧残留进程） |
| 端口 33060 | 被 PID 4080 占用 |
| `tail` 错误日志 | 连续 5 次 `ibdata1 must be writable` 失败 |

### 故障链条

```
my.ini 含不兼容配置 (mysql_native_password)
    → 服务启动失败
        → 手动运行 mysqld.exe 绕过 SCM 启动成功
            → Windows 服务状态仍显示 STOPPED
                → 后续每次 SCM 尝试启动都因 ibdata1 被旧进程锁定而失败
```

### 详情报错时间线

| 时间 | 进程 PID | 结果 | 报错 |
|------|----------|------|------|
| 02:37:11 | 18544 | ❌ | `ibdata1 must be writable`（旧进程 21216 锁住） |
| 02:47:23 | 19064 | ❌ | `unknown variable 'default_authentication_plugin=mysql_native_password'` |
| 02:47:54 | **4080** | ✅ | 手动启动成功 `ready for connections` |
| 02:51:58 | 17416 | ❌ | `ibdata1 must be writable`（PID 4080 锁住） |
| 02:52:41 | 7148 | ❌ | `ibdata1 must be writable`（PID 4080 锁住） |
| 02:54:53 | 12696 | ❌ | `ibdata1 must be writable`（PID 4080 锁住） |
| 02:55:51 | 13056 | ❌ | `ibdata1 must be writable`（PID 4080 锁住） |
| 03:02:43 | 21980 | ❌ | `ibdata1 must be writable`（PID 4080 锁住） |
| **03:04:27** | **23412** | **✅** | `taskkill 4080 → net start MySQL84` 正常启动 |

### 修复操作

```bash
# 1. 杀死残留进程
taskkill //PID 4080 //F

# 2. 确认端口释放
netstat -ano | findstr "3306"

# 3. 正常启动服务
net start MySQL84
```

---

## 二、大一统排查链路（从现象到根因）

遵循 **「先外后内，先简后繁」** 原则。每一步遇到异常即可定位问题。

### 第 0 步：收集基本信息（30 秒三板斧）

```bash
# 斧 1：服务是什么状态？
sc query MySQL84

# 斧 2：端口有没有人在监听？谁在监听？
netstat -ano | findstr "3306"

# 斧 3：日志最近说了什么？
tail -30 "F:\MySQL\MySQL Server 8.4\Data\LAPTOP-K0VIOHAC.err"
```

**解释三板斧结果：**

```
┌─ sc query ─────────────────────────────────────────────────────┐
│ STATE: 4 RUNNING  → 服务正常，跳到「场景 E：能连但性能差」     │
│ STATE: 1 STOPPED  → 继续 Step 1                                │
└────────────────────────────────────────────────────────────────┘

┌─ netstat ──────────────────────────────────────────────────────┐
│ 有 3306，PID 与 sc 一致  → MySQL 运行中，服务也正常            │
│ 有 3306，PID 与 sc 不一致  → 残留进程，跳到「场景 A」          │
│ 有 3306，但服务 STOPPED  → 同上，残留进程                      │
│ 完全没 3306  → MySQL 确实没在跑，继续 Step 1                   │
└────────────────────────────────────────────────────────────────┘

┌─ tail 日志 ────────────────────────────────────────────────────┐
│ 含 ERROR  → 记下错误码，跳到「三、错误码速查表」               │
│ 无 ERROR，最后一行是 "ready for connections" → 曾经成功过      │
│ 无 ERROR，最后一行是 "Shutdown complete" → 上次正常关闭        │
└────────────────────────────────────────────────────────────────┘
```

### Step 1：根据三板斧结果分流

```
三板斧结果                                → 跳转场景
─────────────────────────────────────────────────────
服务 STOPPED + 端口有进程                  → 场景 A：残留进程
服务 STOPPED + 端口空 + 日志有 ERROR       → 场景 B：启动即失败
服务 STOPPED + 端口空 + 日志无异常          → 场景 C：从来没启动过
服务 RUNNING + 端口空                       → 场景 D：服务跑着但端口丢了
服务 RUNNING + 端口有 + 连不上              → 场景 E：能监听到却连不上
服务 RUNNING + 端口有 + 连得上 + 慢/报错    → 场景 F：运行时故障
```

---

### 场景 A：残留进程（服务 STOPPED 但端口有进程）

**症状**：`sc query` 显示 STOPPED，但 `netstat -ano` 显示 3306 被某 PID 占用。

**根因**：mysqld 进程脱离了 SCM 的管控——可能是手动执行了 `mysqld.exe`，也可能是崩溃后 SCM 没跟踪到。

**诊断**：

```bash
# 确认这个进程是谁
tasklist /FI "PID eq <PID>" /FO LIST /V

# 确认锁文件里的 PID
type "F:\MySQL\MySQL Server 8.4\Data\LAPTOP-K0VIOHAC.pid"
```

**修复**：

```bash
# 方案 A1（推荐）：杀掉旧进程，通过 SCM 重启
taskkill /PID <旧PID> /F
net start MySQL84

# 方案 A2：如果旧进程能正常工作，尝试将它重新挂载到 SCM 不太可行，
#         直接用方案 A1 即可。
```

**预防**：
- 永远用 `net start MySQL84` / `net stop MySQL84`，不要直接跑 `mysqld.exe`
- 如果必须手动启动用于调试，用完后 `taskkill` 再 `net start` 恢复正常

---

### 场景 B：启动即失败（服务 STOPPED + 端口空 + 日志有 ERROR）

**症状**：每次启动都 abort，日志里有清晰的 ERROR 行。

**诊断**：

```bash
# 看最近的完整失败周期（一次 start 到 end 为一个周期）
grep -E "start\.|ERROR|Aborting|end\." "F:\MySQL\MySQL Server 8.4\Data\LAPTOP-K0VIOHAC.err" | tail -30
```

**根据 ERROR 类型分流**：

| 日志关键错误 | 子场景 | 跳转 |
|-------------|--------|------|
| `unknown variable` 或 `unknown option` | 配置不兼容 | B1 |
| `ibdata1 must be writable` | 数据文件权限/锁定 | B2 |
| `Can't find file` 或 `No such file` | 文件缺失 | B3 |
| `InnoDB: Tablespace` 相关 | 表空间损坏 | B4 |
| `Port 3306 in use` | 端口冲突 | B5 |
| `Data Dictionary initialization failed` | DD 初始化失败 | B2/B4 |

#### B1：配置不兼容

```bash
# 1. 找到报错的那个变量/选项
grep "unknown variable" "F:\MySQL\MySQL Server 8.4\Data\LAPTOP-K0VIOHAC.err"

# 2. 编辑 my.ini，注释或删除对应行
notepad "F:\MySQL\MySQL Server 8.4\Data\my.ini"

# 3. MySQL 8.4 已移除的常见配置（如果 my.ini 里有这些，全部注释掉）：
#    - default_authentication_plugin = mysql_native_password
#    - query_cache_size
#    - query_cache_type
#    - expire_logs_days（改用 binlog_expire_logs_seconds）

# 4. 重新启动
net start MySQL84
```

#### B2：数据文件权限或锁定

```bash
# 1. 先确认没有其他 mysqld 进程在跑（这是最常见原因）
tasklist | findstr mysqld

# 2. 如果有 → 回到「场景 A」
# 3. 如果没有 → 检查权限
icacls "F:\MySQL\MySQL Server 8.4\Data"

# 4. 确保 NETWORK SERVICE 或 SYSTEM 有完全控制权 (F)
# 如果权限缺失：
icacls "F:\MySQL\MySQL Server 8.4\Data" /grant "NT AUTHORITY\NETWORK SERVICE:(OI)(CI)F" /T

# 5. 重新启动
net start MySQL84
```

#### B3：文件缺失

```bash
# 查看具体哪个文件不存在
grep -E "Can't find|No such file" "F:\MySQL\MySQL Server 8.4\Data\LAPTOP-K0VIOHAC.err"

# 常见缺失文件处理：
# - my.ini 不存在 → 从模板复制或重装
# - ibdata1 不存在 → InnoDB 数据文件丢失，需要从备份恢复
# - 数据库目录不存在 → 确认 datadir 路径是否正确
```

#### B4：表空间损坏

```bash
# 严重故障，通常需要：
# 1. 尝试 InnoDB Recovery 模式（在 my.ini 的 [mysqld] 段添加）：
#    innodb_force_recovery = 1
#    （值从 1 尝试到 6，1 最轻量，6 最强力但数据只读）

# 2. 如果能启动，立即用 mysqldump 导出所有数据
# 3. 导出后关闭 MySQL，删除 Data 目录，重新初始化
# 4. 导入备份

# ⚠️ 此操作风险高，建议先备份现有 Data 目录所有文件
```

#### B5：端口冲突

```bash
# 确认谁占用了 3306
netstat -ano | findstr "3306"
tasklist /FI "PID eq <占用PID>" /FO LIST

# 如果是另一个 mysqld → 回到「场景 A」
# 如果是其他程序 → 改 my.ini 里的 port 或用 netstat 找出对方并处理
```

---

### 场景 C：从来没启动过（全新安装/初始化失败）

```bash
# 1. 确认 Data 目录是否已初始化（是否有 ibdata1, mysql/ 子目录等）
ls "F:\MySQL\MySQL Server 8.4\Data"

# 2. 如果 Data 目录是空的或缺失关键文件 → 初始化
"F:\MySQL\MySQL Server 8.4\bin\mysqld.exe" --initialize-insecure --console

# 3. 安装 Windows 服务（如果还没有）
"F:\MySQL\MySQL Server 8.4\bin\mysqld.exe" --install MySQL84 --defaults-file="F:\MySQL\MySQL Server 8.4\Data\my.ini"

# 4. 启动
net start MySQL84
```

---

### 场景 D：服务 RUNNING 但端口不通

```bash
# 1. 再次确认端口
netstat -ano | findstr "3306"

# 2. 检查 my.ini 里 bind-address 是不是绑到了奇怪地址
grep -i "bind-address" "F:\MySQL\MySQL Server 8.4\Data\my.ini"
# 正常应该是 bind-address=0.0.0.0 或者 bind-address=*

# 3. 检查 Windows 防火墙
netsh advfirewall firewall show rule name=all | findstr -i mysql
# 如果没有规则，添加入站规则：
netsh advfirewall firewall add rule name="MySQL 3306" dir=in action=allow protocol=TCP localport=3306
```

---

### 场景 E：能监听但连不上

```bash
# 1. 本地测试（绕过网络层）
"F:\MySQL\MySQL Server 8.4\bin\mysql.exe" -u root -p -h 127.0.0.1

# 2. 如果本地能连，远程不能连 → 检查用户 host 权限
"F:\MySQL\MySQL Server 8.4\bin\mysql.exe" -u root -p -e "SELECT user, host FROM mysql.user;"

# 3. 如果本地也不能连（Access denied）→ 重置 root 密码：
#    3a. 停掉服务
net stop MySQL84
#    3b. 创建密码重置 SQL 文件（内容见下）
#    3c. 用 --init-file 启动
"F:\MySQL\MySQL Server 8.4\bin\mysqld.exe" --defaults-file="F:\MySQL\MySQL Server 8.4\Data\my.ini" --init-file="F:\MySQL\reset-pwd.sql"
```

**reset-pwd.sql 内容**：
```sql
ALTER USER 'root'@'localhost' IDENTIFIED BY '你的新密码';
```

---

### 场景 F：运行时故障（服务正常但使用中出问题）

```bash
# 1. 查看当前连接数和状态
mysql -u root -p -e "SHOW PROCESSLIST;"
mysql -u root -p -e "SHOW STATUS LIKE 'Threads%';"

# 2. 查看慢查询
mysql -u root -p -e "SHOW VARIABLES LIKE 'slow_query_log%';"

# 3. 查看 InnoDB 状态
mysql -u root -p -e "SHOW ENGINE INNODB STATUS\G"

# 4. 检查磁盘空间
mysql -u root -p -e "SELECT table_schema, ROUND(SUM(data_length+index_length)/1024/1024/1024,2) AS 'Size(GB)' FROM information_schema.tables GROUP BY table_schema ORDER BY 2 DESC;"

# 5. 检查是否有锁等待
mysql -u root -p -e "SELECT * FROM information_schema.INNODB_TRX\G"
mysql -u root -p -e "SELECT * FROM performance_schema.data_lock_waits\G"
```

---

## 三、错误码速查表

| 错误码 | 关键文本 | 最常见原因 | 跳转 |
|--------|---------|-----------|------|
| MY-000067 | `unknown variable` | my.ini 中有 MySQL 8.4 已移除的配置项 | B1 |
| MY-000068 | `unknown option` | 启动参数包含无效选项（如 `--install` 被传给了服务） | B1 |
| MY-010147 | `Too many arguments` | mysqld 命令行参数格式错误 | B1 |
| MY-012271 | `ibdata1 must be writable` | 另一个 mysqld 进程锁住了数据文件 | A / B2 |
| MY-012278 | `ibdata1 must be writable` | 同上（InnoDB 表空间写入失败） | A / B2 |
| MY-010334 | `Failed to initialize DD Storage Engine` | InnoDB 初始化失败导致 Data Dictionary 无法加载 | B2 / B4 |
| MY-010020 | `Data Dictionary initialization failed` | DD 初始化失败的顶层错误 | B2 / B4 |
| MY-010119 | `Aborting` | 通用中止信号，需看上一条 ERROR | 看上一条 |
| MY-010068 | `CA certificate ca.pem is self signed` | **这只是 Warning，不影响使用**，可以忽略 | — |
| MY-010931 | `ready for connections` | **这不是错误！** 成功启动的标志 | — |

---

## 四、常用命令速查

### 服务管理

```bash
sc query MySQL84                          # 查看服务状态
net start MySQL84                         # 启动
net stop MySQL84                          # 停止
sc qc MySQL84                             # 查看服务配置详情
```

### 进程与端口

```bash
netstat -ano | findstr "3306"             # 查 3306 端口占用
netstat -ano | findstr "33060"            # 查 33060 端口占用（X Plugin）
tasklist | findstr mysqld                 # 列出所有 mysqld 进程
tasklist /FI "PID eq <PID>" /FO LIST /V   # 查指定 PID 的进程详情
taskkill /PID <PID> /F                    # 强制杀死指定 PID
```

### 日志

```bash
# 查看最后 N 行
tail -50 "F:\MySQL\MySQL Server 8.4\Data\LAPTOP-K0VIOHAC.err"

# 只看错误
grep "ERROR" "F:\MySQL\MySQL Server 8.4\Data\LAPTOP-K0VIOHAC.err"

# 按启动周期看（一次 start 到 end）
grep -E "start\.|ERROR|Aborting|end\." "F:\MySQL\MySQL Server 8.4\Data\LAPTOP-K0VIOHAC.err"

# 实时跟踪日志（调试用）
tail -f "F:\MySQL\MySQL Server 8.4\Data\LAPTOP-K0VIOHAC.err"
```

### 配置文件

```bash
# 路径
F:\MySQL\MySQL Server 8.4\Data\my.ini

# 查看配置
cat "F:\MySQL\MySQL Server 8.4\Data\my.ini"

# 查找特定配置项
grep -i "<关键词>" "F:\MySQL\MySQL Server 8.4\Data\my.ini"
```

### 数据目录

```bash
# 查看数据目录内容
ls -la "F:\MySQL\MySQL Server 8.4\Data"

# 检查权限
icacls "F:\MySQL\MySQL Server 8.4\Data"

# 修复权限（赋予 NETWORK SERVICE 完全控制）
icacls "F:\MySQL\MySQL Server 8.4\Data" /grant "NT AUTHORITY\NETWORK SERVICE:(OI)(CI)F" /T

# 查磁盘剩余空间
df -h /f
```

### 连接测试

```bash
# ping（只测试是否 accept 连接）
"F:\MySQL\MySQL Server 8.4\bin\mysqladmin.exe" -u root -p ping

# 完整命令行连接
"F:\MySQL\MySQL Server 8.4\bin\mysql.exe" -u root -p -h 127.0.0.1

# 用密码连接
"F:\MySQL\MySQL Server 8.4\bin\mysql.exe" -u root -p"你的密码"
```

---

## 五、关键文件路径清单

| 文件 | 路径 |
|------|------|
| 错误日志 | `F:\MySQL\MySQL Server 8.4\Data\LAPTOP-K0VIOHAC.err` |
| 配置文件 | `F:\MySQL\MySQL Server 8.4\Data\my.ini` |
| PID 文件 | `F:\MySQL\MySQL Server 8.4\Data\LAPTOP-K0VIOHAC.pid` |
| 二进制文件 | `F:\MySQL\MySQL Server 8.4\bin\mysqld.exe` |
| 客户端 | `F:\MySQL\MySQL Server 8.4\bin\mysql.exe` |
| 管理工具 | `F:\MySQL\MySQL Server 8.4\bin\mysqladmin.exe` |
| 数据目录 | `F:\MySQL\MySQL Server 8.4\Data\` |

---

## 六、MySQL 8.4 升级注意事项

如果是从 MySQL 5.7 / 8.0 升级上来的，以下配置项已被移除，**my.ini 中不能出现**：

```ini
# ❌ 以下全部在 8.4 中不存在，必须删除或注释：
default_authentication_plugin = mysql_native_password
query_cache_size = ...
query_cache_type = ...
expire_logs_days = ...
log_bin_use_v1_row_events = ...
master_info_repository = ...
relay_log_info_repository = ...
slave_parallel_type = ...
```

---

## 七、预防性建议

1. **始终用 `net start/stop MySQL84`**，不要直接执行 `mysqld.exe` 或 `mysqld --install`
2. **修改 my.ini 后用服务启动验证**：`net start MySQL84 && tail -5 "路径.err"`
3. **定期备份**：至少保留一份 `Data` 目录快照
4. **磁盘空间监控**：InnoDB 需要足够空间扩展 ibdata1 和 ib_logfile
5. **Windows 更新后验证**：某些累积更新可能重置文件权限
6. **数据盘不要放 C 盘**（你已经做到了，放在 F 盘）
