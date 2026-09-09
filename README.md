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

NovaXinWei (新信微) 与 [Novahaku (刃)](https://github.com/novaestellar/novahaku) 构成完整的 **侦察→利用** 攻击链。新信微负责主动网络侦察与数据采集,Novahaku负责漏洞发现、利用与报告。两者均为 Hermes Agent 技能,共享 `engagement/` 目录进行数据传递。

---

### Novahaku 8大领域能力

| # | 领域 | 说明 | 核心工具/输出 |
|---|------|------|---------------|
| 1 | **Web测试** | 14模块测试集(headers、exposed、cors、methods、admin、xss、sqli、ssrf、ssti、traversal、redirect、info、dirfuzz、https) + 竞态条件 + JWT分析/伪造/暴力破解 | `webtest.py`、`race_test.py`、`jwt_test.py`、48个payload参考 |
| 2 | **提示工程** | 121项技术,7大分类(Boundary、Priming、Identity、Encoding、Multi-Provider、Iterative、Stream),4级锁定命令(basic 85%→triple 95%),AES-256-GCM加密Vault | `loader.py`、prompt-arsenal模板、method-reference |
| 3 | **攻击框架(v41)** | v41文言攻击提示(古典中文),5个注入面分析,跨模型评估矩阵(8/8已验证),Hermes预填充集成 | `test-novahaku.py`、claude-config-bundle |
| 4 | **重构引擎(Reframe)** | 48个触发词→安全措辞映射,SessionState持久化,输出合同(ROUTE/RESULT/CHANGED/VERIFY/NEXT),每模型人格锁定 | `reframe_cli.py`、prompt-arsenal、operations-plan |
| 5 | **Windows逆向 + EDR绕过** | 反调试绕过(IsDebuggerPresent、NtQueryInformationProcess、RDTSC)、内联/IAT钩子、游戏安全(Tencent ACE、BattlEye、EAC)、x64dbg/IDA/Ghidra工作流; EDR/AV绕过: AMSI bypass(DLL patching、memory patching、.NET reflection)、ETW patching、User-mode hook detection + direct syscalls(Hell's Gate、SysWhispers、FreshyCalls)、Defender bypass、CrowdStrike/SentinelOne evasion | `windows-re.md`、反调试工作流、SysWhispers模板 |
| 6 | **二进制利用(Pwn Chain)** | 栈溢出、格式化字符串、堆利用(UAF/DF/OF)、ret2libc/ret2csu/one_gadget、64位栈对齐(movaps fix); 内核pwn: kROP、SMEP/SMAP绕过、KASLR leak、modprobe_path; 工具链: pwntools + GEF/pwndbg + ROPgadget + one_gadget + libc-database | `pwn-chain.md`、pwntools脚本模板 |
| 7 | **身份与人格** | Haku人格(优雅+锐利+尊重),558个few-shot示例,280个安全术语映射,5种情绪状态,10条反漂移规则 | `few-shots-primary.md`、persona定义 |
| 8 | **OSINT与被动侦察** | 子域名枚举、端口扫描、技术栈指纹(Wappalyzer)、公开数据源(GitHub/Pastebin/Shodan/Censys/Greynoise)、CT日志分析、WHOIS/DNS查询、Credential泄露检查(HIBP、IntelX) | `offensive-osint/`、`osint-methodology/`、`email-domain-security/`、`cloud-saas-exposure/`、`identity-provider-recon/`、`org-attack-surface/` |

---

### 完整协同工作流: 侦察→利用全链路

```
用户: "全面测试 example.com"
  │
  ▼
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
阶段1: NovaXinWei (新信微) — 主动侦察
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  │
  ├─ 1a. 平台路由侦察
  │   - 15平台API路由 → 发现社交媒体/论坛/代码托管中的目标信息
  │   - 内容安全检查 → 6层提示注入检测 + URL掩码保护
  │
  ├─ 1b. WAF绕过抓取
  │   - curl_cffi TLS指纹模拟(Safari/Chrome/Edge/Firefox)
  │   - Playwright无头浏览器回退
  │   - URL变换(移动端、JSON、RSS)
  │
  ├─ 1c. Dork数据库查询
  │   - Shodan 126模式(Web Server/DB/IoT/Cloud/Industrial/Network/Security)
  │   - GitHub 234模式(Credentials/Config/Keys/CI-CD/Cloud等10分类)
  │
  ├─ 1d. 并行批量抓取
  │   - ThreadPoolExecutor可配置工作线程
  │   - 自学习系统记录成功模式,下次自动优化
  │
  ▼
  输出: JSON格式侦察报告 (engagement/<target>/recon.json)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  │
  ▼
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
阶段2: Novahaku (刃) — 漏洞发现 + 利用
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  │
  ├─ 2a. 接收侦察数据
  │   - 读取 engagement/<target>/recon.json
  │   - 解析: 子域名、端口、技术栈、WAF类型、暴露面
  │
  ├─ 2b. 被动侦察补充 (OSINT)
  │   - CT日志分析、WHOIS/DNS查询
  │   - Credential泄露检查(HIBP、IntelX)
  │   - 云暴露检测(S3 bucket、Azure、GCP)
  │
  ├─ 2c. Web漏洞测试
  │   - 根据技术栈自动选择测试模块
  │   - XSS/SQLi/SSRF/SSTI/IDOR/CSRF/RCE...
  │   - JWT分析 + 竞态条件测试
  │
  ├─ 2d. 深度利用 (如需要)
  │   - Windows逆向 + EDR绕过 (本地目标)
  │   - Pwn Chain (二进制漏洞利用)
  │   - 攻击框架v41 (AI系统测试)
  │
  ├─ 2e. 报告生成
  │   - 结构化漏洞报告 + PoC代码
  │   - 修复建议
  │
  ▼
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  │
  ▼
阶段3: 结果交付用户
  - engagement/<target>/report.md (完整报告)
  - engagement/<target>/poc/ (PoC代码)
  - engagement/<target>/recon.json (侦察原始数据)
```

---

### 新信微频道输出 → 刃测试模块 映射表

| 新信微输出数据 | 来源渠道/功能 | Novahaku接收模块 | 测试方向 |
|----------------|--------------|------------------|----------|
| **子域名列表** | Shodan Dorks + GitHub Dorks + crt.sh | OSINT被动侦察 | 子域名枚举→扩大攻击面 |
| **端口/服务信息** | Shodan Dorks (126模式) | OSINT + Web测试 | 服务指纹→选择测试向量 |
| **技术栈指纹** | WAF绕过抓取链(Wappalyzer) | Web测试(14模块) | 根据框架选择: Laravel审计/Supabase审计/Next.js审计 |
| **WAF类型** | WAF检测器(waf_detector.py) | Web测试(WAF绕过) | 绕过策略: payload变形、编码绕过、时间盲注 |
| **社交媒体内容** | 15平台API路由 | OSINT + 提示工程 | 信息泄露→社工素材、暴露凭据 |
| **代码仓库数据** | GitHub Dorks (234模式) | Pwn Chain + 攻击框架 | 泄露私钥→SSH认证; 泄露密码→认证绕过; CI/CD→供应链攻击 |
| **IoT/SCADA设备** | Shodan Dorks (IoT/Industrial分类) | Windows逆向 + EDR绕过 | 固件逆向、工控协议漏洞 |
| **云配置** | Shodan Dorks (Cloud分类) + GitHub Dorks (Cloud) | OSINT(Cloud/SaaS Exposure) | S3桶、Azure Blob、GCP Storage暴露 |
| **RSS/Feed数据** | RSS通用频道 | 重构引擎(Reframe) | 内容分析→检测AI生成内容、信息篡改 |
| **论坛/社区情报** | V2EX/博客园/CSDN/SegmentFault | 提示工程 + 攻击框架 | 社区漏洞讨论→复制攻击向量、0day情报 |
| **凭据泄露** | GitHub Dorks (Credentials/Keys分类) | OSINT(Credential Check) | 泄露密码/Token→认证测试、账户接管 |
| **API端点** | Web抓取 + 平台路由 | Web测试(dirfuzz + methods) | API枚举→未授权访问、IDOR、GraphQL注入 |
| **邮件域名信息** | Whois/DNS + Dorks | OSINT(Email Domain Security) | SPF/DKIM/DMARC配置→邮件欺骗 |
| **内部文档** | GitHub Dorks (Internal/Backup分类) | 攻击框架 + Pwn Chain | 信息泄露→社工、凭证提取、内部网络拓扑 |

---

### 协同约定

| 约定 | 说明 |
|------|------|
| **数据传递格式** | JSON,文件存放于 `engagement/<target>/` 目录 |
| **目标命名** | 统一使用目标域名作为根目录名 |
| **上下文传递** | 通过 Hermes skill chaining,用户意图自动路由 |
| **互不侵入** | 新信微不写exploit代码,刃不写爬虫代码 |
| **侦察输出结构** | `recon.json` 包含: `subdomains[]`、`ports[]`、`tech_stack[]`、`waf_type`、`platforms[]`、`dorks_hits[]`、`raw_content[]` |
| **测试输入约定** | 读取 `recon.json` 的 `subdomains`、`ports`、`tech_stack` 字段,据此自动选择测试模块 |

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
