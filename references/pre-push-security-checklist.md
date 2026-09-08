# GitHub 推送前安全检查清单 (Pre-Push Security Checklist)

## 必须排除的文件

### 密钥和凭证
- `.env` — 环境变量文件，包含 API 密钥
- `*.key`, `*.pem` — 私钥文件
- `credentials/` — 凭证目录
- `secrets/` — 敏感配置目录
- `token*` — 令牌文件

### 构建产物
- `__pycache__/` — Python 编译缓存
- `*.pyc` — Python 字节码
- `.pytest_cache/` — 测试缓存
- `.coverage` — 覆盖率报告
- `dist/`, `build/` — 构建输出
- `*.egg-info/` — 包信息

### IDE 和编辑器
- `.idea/` — JetBrains IDE 配置
- `.vscode/` — VS Code 配置
- `.devcontainer/` — 开发容器配置

### 其他
- `node_modules/` — Node.js 依赖
- `*.log` — 日志文件
- `*.tmp` — 临时文件

## 推荐保留的文件

- `.env.example` — 环境变量示例（必须）
- `references/` — 文档参考
- `dorks/` — 攻击模式库
- `templates/` — 模板文件
- `docs/` — 文档目录

## 检查命令

```bash
# 1. 检查是否有敏感文件被跟踪
git ls-files | grep -E '\.(key|pem|env)$' || echo "✅ 无敏感文件"

# 2. 检查是否有缓存目录被跟踪
git ls-files | grep -E '(__pycache__|\.pytest_cache|\.coverage)' || echo "✅ 无缓存文件"

# 3. 检查 .gitignore 是否包含必要条目
for pattern in ".env" "*.key" "*.pem" "__pycache__/" ".pytest_cache/" ".coverage" "dist/" "build/"; do
  grep -q "$pattern" .gitignore 2>/dev/null && echo "✅ $pattern" || echo "❌ 缺少 $pattern"
done

# 4. 检查是否有大文件
git ls-files -z | xargs -0 -I{} du -b {} 2>/dev/null | sort -rn | head -10

# 5. 最终检查
echo "=== Git 状态 ==="
git status
```

## 文档要求 (Mandarin)

所有公开文档必须使用中文 (Mandarin):
- README.md: 项目概述、快速开始、安装指南、功能说明、架构图
- CHANGELOG.md: 版本更新记录
- CONTRIBUTING.md: 贡献指南
- .env.example: 环境变量示例（必须包含所有可能的配置项）
