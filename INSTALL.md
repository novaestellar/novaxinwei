# NovaXinWei (新信微) — 安装指南

## 前置条件

- Python 3.10+
- pip 包管理器

## 核心依赖安装

```bash
# 核心依赖
pip install curl_cffi>=0.15.0 httpx>=0.27.0 feedparser>=6.0 loguru>=0.7 rich>=13.0 pyyaml>=6.0

# CVE Scraper + GitHub Pages Enum 需要
pip install requests
```

## 可选依赖

```bash
# YouTube 提取
pip install yt-dlp>=2024.1

# Playwright 回退 (B站/LinkedIn等)
pip install playwright
playwright install chromium
```

## 安装步骤

### 方法1: 克隆仓库

```bash
git clone https://github.com/novaestellar/novaxinwei.git
cd novaxinwei
pip install -r requirements.txt  # 如果存在
```

### 方法2: Hermes Agent 技能安装

放入 `~/.hermes/skills/security/novaxinwei/` 即可自动加载。

## 环境变量配置

```bash
# 复制模板
cp .env.example .env

# 至少填写 GitHub Dorks 配置
# GH_TOKEN=""  (可选, 提升 GitHub API 限额 60/h → 5000/h)
```

## 验证安装

```bash
# 检查版本
python -m novaxinwei check

# 测试 CVE Scraper (无需认证)
python tools/cve/cve_scraper.py

# 测试 CVE 自动导出到 Novahaku
python tools/cve/export_to_novahaku.py

# 测试 GitHub Pages 枚举
python tools/github_pages/github_pages_enum.py --username <user> --repos <repo1,repo2>

# 测试 WayAI URL 采集
python tools/wayai/wayai.py --domain example.com
```

## 协同流水线 (与 Novahaku)

```bash
# Pipeline 1: Wayback → Secret Scan
python tools/wayai/wayai.py --domain target.com | \
  python <novahaku-path>/testing/offensive-osint/scripts/secret_scan.py --stdin

# Pipeline 2: CVE Feed 自动导出
python tools/cve/cve_scraper.py --severity critical
python tools/cve/export_to_novahaku.py
```

## 故障排除

| 问题 | 解决方案 |
|------|----------|
| `curl_cffi` 安装失败 | 升级 pip: `pip install --upgrade pip` |
| GitHub API 403 | 配置 `GH_TOKEN` 环境变量 |
| Playwright 不可用 | `playwright install chromium` |
| CVE feed 导出失败 | 检查 Novahaku 路径是否存在 |

---
**NovaXinWei v1.1.0** | Author: novalabs | License: MIT
