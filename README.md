<p align="center">
  <img src="assets/logo.svg" alt="NovaXinWei Logo" width="150">
</p>

# NovaXinWei (新信微)

> **统一网络侦察引擎** — WAF绕过 · 并行抓取 · Dork数据库 · 15平台路由 · 内容安全

<p align="center">
  <strong>SeaGull Security Lab</strong><br>
  静观其变,以微知著 — 新信微
</p>

---

## 📋 描述

NovaXinWei 是一个统一的网络侦察引擎，整合了 **4大核心能力** 到单一技能包中。支持 WAF绕过抓取、15平台API路由、Shodan/GitHub Dork数据库查询和并行批量抓取。

专为 Hermes Agent 平台设计，与 [Novahaku](https://github.com/novaestellar/novahaku) 协同工作：**新信微负责侦察发现，Novahaku负责漏洞利用。**

### 核心特性

| 特性 | 说明 |
|------|------|
| 🛡️ WAF绕过抓取链 | curl_cffi TLS指纹模拟 + Playwright无头浏览器回退 |
| 🌐 15平台API路由 | Reddit、YouTube、X/Twitter、Threads、小红书、B站、V2EX、Facebook、Instagram、LinkedIn、博客园、CSDN、SegmentFault、SoGitee、Codeberg |
| 🔍 Dork数据库 | Shodan 126模式 + GitHub 234模式，10大分类 |
| ⚡ 并行抓取 | ThreadPoolExecutor，可配置工作线程数 |
| 🧠 自学习系统 | 4层反馈闭环，自动记录成功模式 |
| 🔒 内容安全 | 6层提示注入检测 + URL掩码保护 |
| 🌍 无站点规则 | 引擎不存储站点特定数据，全部运行时注入 |

---

## 🚀 快速安装

### 前置条件

```bash
# Python 3.10+
python --version

# 核心依赖
pip install curl_cffi httpx feedparser loguru rich pyyaml

# 可选依赖 (YouTube提取)
pip install yt-dlp

# 可选依赖 (Playwright回退, 用于B站/LinkedIn等)
pip install playwright
playwright install chromium
```

### 安装

```bash
# 方法1: 克隆仓库
git clone https://github.com/novaestellar/novaxinwei.git
cd novaxinwei
pip install -r requirements.txt

# 方法2: Hermes Agent 自动安装
# (放入 ~/.hermes/skills/web/novaxinwei/ 即可)
```

### 环境变量配置

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑配置 (至少填写 GitHub Dorks 配置)
vim .env
```

### 验证安装

```bash
# 检查版本
python -m novaxinwei --help

# 检查频道可用性
python -m novaxinwei check

# 测试抓取
python -m novaxinwei fetch https://httpbin.org/get

# 测试 Dork 查询
python -m novaxinwei dorks shodan apache
```

---

## 🧩 目录结构

```
novaxinwei/
├── __init__.py              # 包入口
├── __main__.py              # CLI 入口
├── cli.py                   # 命令行接口
├── engine/                  # 核心引擎
│   ├── fetch_chain.py       # WAF绕过抓取链
│   ├── phase0.py            # 15平台API路由
│   ├── waf_detector.py      # WAF检测器
│   ├── validators.py        # 验证器 (6层)
│   ├── url_transforms.py    # URL变换
│   ├── content_safety.py    # 内容安全 (提示注入检测)
│   ├── url_masking.py       # URL掩码
│   ├── transport.py         # HTTP传输层
│   ├── executor.py          # Playwright执行器
│   ├── learning.py          # 自学习系统
│   ├── observations_log.py  # 观察日志
│   ├── safety.py            # 安全策略
│   ├── bias_check.py        # 偏见检查
│   ├── x_search.py          # X/Twitter搜索
│   ├── x_search_io.py       # X搜索IO
│   ├── x_search_types.py    # X搜索类型
│   └── templates/           # Playwright模板
│       ├── nodriver_fetch.py
│       └── patchright_fetch.py
├── channels/                # 15平台频道
│   ├── __init__.py          # 频道注册表
│   ├── base.py              # 基类
│   ├── utils.py             # 工具函数
│   ├── reddit.py            # Reddit
│   ├── twitter.py           # X/Twitter
│   ├── youtube.py           # YouTube
│   ├── threads.py           # Threads
│   ├── xiaohongshu.py       # 小红书
│   ├── bilibili.py          # B站
│   ├── v2ex.py              # V2EX
│   ├── facebook.py          # Facebook
│   ├── instagram.py         # Instagram
│   ├── linkedin.py          # LinkedIn
│   ├── nodeseek.py          # NodeSeek
│   ├── nodeloc.py           # NodeLoc
│   ├── pojie.py             # 52PoJie
│   ├── rss.py               # RSS通用
│   └── web.py               # Web兜底
├── dorks/                   # Dork数据库
│   ├── shodan-dorks.yaml    # Shodan 126模式
│   ├── github-dorks.txt     # GitHub 234模式
│   └── github_dorks/        # GitHub Dorks CLI
│       ├── __init__.py
│       ├── __main__.py
│       └── cli.py
├── references/              # 参考文档 (21个)
│   ├── tls-impersonate.md   # TLS指纹模拟
│   ├── playwright.md        # Playwright指南
│   ├── social.md            # 社交平台API
│   ├── twitter.md           # Twitter API
│   ├── rss.md               # RSS指南
│   └── ...                  # 更多参考
├── SKILL.md                 # Hermes技能定义
├── .env.example             # 环境变量模板
├── .gitignore               # Git忽略配置
└── LICENSE                  # MIT许可证
```

---

## ⚡ 能力详解

### 1. WAF绕过抓取链

4阶段抓取策略，自动选择最优路径：

```
阶段0: 平台API路由 (15平台)
  ↓ 失败
阶段1: URL变换 (移动端、JSON、RSS)
  ↓ 失败
阶段2: TLS指纹模拟 (curl_cffi Safari/Chrome)
  ↓ 失败
阶段3: Playwright无头浏览器回退
```

**支持的TLS指纹:**
- Safari (默认)
- Chrome
- Edge
- Firefox

**使用方式:**
```bash
# 基础抓取
python -m novaxinwei fetch https://example.com

# 指定TLS指纹
python -m novaxinwei fetch https://example.com --impersonate chrome

# 强制Playwright回退
python -m novaxinwei fetch https://example.com --playwright
```

### 2. 15平台API路由

| 平台 | 路由方式 | 备注 |
|------|----------|------|
| Reddit | RSS + JSON + oembed | 3层回退 |
| YouTube | oembed + yt-dlp | 视频提取 |
| X/Twitter | oembed + HTML | 需要Cookie |
| Threads | meta标签提取 | 视频版本解析 |
| 小红书 | 移动API + HTML | 反爬虫绕过 |
| B站 | HTML + Referer | 需要Cookie (412) |
| V2EX | API + HTML | 官方API优先 |
| Facebook | oembed + HTML | 需要登录 |
| Instagram | oembed + HTML | 需要登录 |
| LinkedIn | oembed + HTML | 999反爬虫 |
| 博客园 | RSS | 直接解析 |
| CSDN | HTML | 文章提取 |
| SegmentFault | HTML | 问答提取 |
| SoGitee | HTML | 搜索页面 |
| Codeberg | RSS | 直接解析 |

**使用方式:**
```bash
# 检查所有频道可用性
python -m novaxinwei check

# 检查单个频道
python -m novaxinwei check reddit
```

### 3. Dork数据库

#### Shodan Dorks (126模式, 7分类)

| 分类 | 模式数 | 说明 |
|------|--------|------|
| Web Server | 18 | Apache、Nginx、IIS等 |
| Database | 15 | MySQL、MongoDB、Redis等 |
| IoT | 20 | 摄像头、路由器、工控设备 |
| Cloud | 12 | AWS、Azure、GCP |
| Industrial | 15 | SCADA、PLC、HMI |
| Network | 16 | VPN、防火墙、代理 |
| Security | 30 | 漏洞、暴露服务 |

#### GitHub Dorks (234模式, 10分类)

| 分类 | 模式数 | 说明 |
|------|--------|------|
| Credentials | 28 | 密码、Token、API密钥 |
| Config | 25 | 配置文件、环境变量 |
| Database | 20 | SQL转储、数据库备份 |
| Keys | 22 | 私钥、证书、SSH密钥 |
| Logs | 18 | 日志文件、调试信息 |
| Backup | 15 | 备份文件、压缩包 |
| Internal | 20 | 内部文档、API文档 |
| CI/CD | 18 | GitHub Actions、GitLab CI |
| Cloud | 18 | AWS、Azure、GCP配置 |
| Misc | 30 | 其他敏感信息 |

**使用方式:**
```bash
# Shodan Dork查询
python -m novaxinwei dorks shodan apache

# GitHub Dork查询
python -m novaxinwei dorks github password

# 指定分类
python -m novaxinwei dorks shodan --category database
```

### 4. 并行抓取

```bash
# 并行抓取多个URL
python -m novaxinwei fetch-parallel url1 url2 url3 --workers 5

# Python API
from novaxinwei.channels import fetch_parallel
results = fetch_parallel(["url1", "url2", "url3"], max_workers=5)
```

---

## 🔧 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `GH_USER` | — | GitHub用户名 (Dorks用) |
| `GH_PWD` | — | GitHub密码 (Dorks用) |
| `GH_TOKEN` | — | GitHub Token (Dorks用) |
| `XAI_API_KEY` | — | xAI API密钥 (X搜索用) |
| `NOVAXINWEI_AUTO_INSTALL` | `0` | 自动安装Playwright |
| `NOVAXINWEI_JITTER_MS_MIN` | `150` | 请求抖动最小值 (ms) |
| `NOVAXINWEI_JITTER_MS_MAX` | `400` | 请求抖动最大值 (ms) |
| `NOVAXINWEI_NO_SESSION_POOL` | `0` | 禁用Session池 |
| `NOVAXINWEI_LEARN` | `1` | 启用自学习 |
| `NOVAXINWEI_LEARN_TTL_DAYS` | `30` | 学习数据TTL (天) |
| `NOVAXINWEI_LEARN_MAX` | `500` | 学习数据最大条目 |
| `NOVAXINWEI_ALLOW_PRIVATE` | `0` | 允许私有地址 (仅测试) |
| `NOVAXINWEI_OBSERVATIONS_DIR` | — | 自定义Observations目录 |
| `NOVAXINWEI_SEARCH_XAI` | `auto` | xAI搜索开关 |

---

## 🔗 与Novahaku协同

NovaXinWei 与 [Novahaku](https://github.com/novaestellar/novahaku) 构成完整攻击链：

```
NovaXinWei (新信微)          Novahaku (刃)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
侦察发现                     漏洞利用
  ├─ 15平台路由               ├─ Web渗透测试
  ├─ WAF绕过抓取              ├─ 提示工程
  ├─ Dork数据库               ├─ 攻击框架
  ├─ 并行抓取                 ├─ 逆向工程
  └─ 内容安全                 └─ 请求重构
```

**协同流程:**
1. 新信微发现目标 → 抓取内容
2. 新信微提取信息 → 传递给刃
3. 刃执行渗透测试 → 发现漏洞
4. 刃开发利用代码 → 完成攻击链

---

## 🛡️ 安全说明

### 内容安全

- **6层提示注入检测:** 自动识别并包装用户内容中的恶意指令
- **URL掩码保护:** 输出时自动掩码敏感URL参数
- **无站点规则:** 引擎不存储站点特定数据，全部运行时注入

### 使用注意

- ⚠️ `NOVAXINWEI_ALLOW_PRIVATE=1` 仅限本地测试，生产环境必须关闭
- ⚠️ GitHub Token 仅用于Dork查询，不要用于其他用途
- ⚠️ 所有观察数据存储在本地，不会上传到任何服务器

---

## 📚 参考文档

`references/` 目录包含21个详细参考文档：

| 文档 | 说明 |
|------|------|
| `tls-impersonate.md` | TLS指纹模拟技术详解 |
| `playwright.md` | Playwright回退指南 |
| `social.md` | 社交平台API汇总 |
| `twitter.md` | Twitter/X API详解 |
| `rss.md` | RSS/Atom解析指南 |
| `json-api.md` | JSON API抓取模式 |
| `metadata.md` | 元数据提取方法 |
| `video.md` | 视频提取指南 |
| `media.md` | 媒体资源抓取 |
| `fallback.md` | 回退策略详解 |
| `setup-*.md` | 各平台设置指南 |

---

## 🤝 贡献

欢迎贡献代码、报告Bug或提出建议。

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m '添加了某个特性'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

---

## 📄 许可证

本项目采用 MIT 许可证 — 详见 [LICENSE](LICENSE) 文件。

---

## 🏷️ 标签

`#网络侦察` `#WAF绕过` `#Dork查询` `#并行抓取` `#社交平台` `#Hermes技能` `#安全研究`
