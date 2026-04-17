# Ads Skill — Google Ads CLI

使用 `ads-skill` 命令行工具查看 Google Ads 广告账户数据。

---

## 初始化配置

**首次使用前，先创建 `.env` 文件：**

```bash
cp .env.example .env
# 然后编辑 .env，填入下方三项真实凭证
```

`.env` 已被 `.gitignore` 屏蔽，不会提交到 git。

---

## 凭证配置

运行任何命令前，先确认 `.env` 中以下三项已填写。也可直接设置同名环境变量。

### 1. Developer Token

**用途：** 访问 Google Ads API 的必要令牌，在 Google Ads 账户的 API Center 申请。

**如何获取：**
1. 登录 Google Ads → 工具与设置 → API Center
2. 申请开发者令牌（测试账户可立即获得测试级别令牌）

**配置方式：**
```bash
# 在 .env 中填写（推荐）
ADS_DEVELOPER_TOKEN=your-developer-token

# 或直接设置环境变量
export ADS_DEVELOPER_TOKEN="your-developer-token"
```

> 如果用户未配置 Developer Token，**主动询问**：
> "请提供您的 Google Ads Developer Token（在 Google Ads → 工具与设置 → API Center 获取）"

---

### 2. OAuth2 Client ID 和 Client Secret

**用途：** OAuth2 应用凭证，在 Google Cloud Console 创建。

**如何获取：**
1. 打开 [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. 创建凭证 → OAuth 客户端 ID → 应用类型选"桌面应用"
3. 在已授权重定向 URI 中添加：`http://localhost:8086/callback`
4. 下载或复制 Client ID 和 Client Secret

**配置方式：**
```bash
# 在 .env 中填写（推荐）
ADS_CLIENT_ID=your-client-id.apps.googleusercontent.com
ADS_CLIENT_SECRET=GOCSPX-your-client-secret

# 或直接设置环境变量
export ADS_CLIENT_ID="your-client-id.apps.googleusercontent.com"
export ADS_CLIENT_SECRET="GOCSPX-your-client-secret"
```

> 如果用户未配置 Client ID 或 Secret，**主动询问**：
> "请提供您的 Google Cloud OAuth2 凭证：\n- Client ID（格式：xxxxx.apps.googleusercontent.com）\n- Client Secret（格式：GOCSPX-xxxxx）\n\n在 Google Cloud Console → API与服务 → 凭证 中创建。"

---

## OAuth2 登录与 Token 管理

### 首次登录

```bash
ads-skill auth login
```

- 自动打开浏览器完成 Google 授权
- 本地 8086 端口接收回调（`http://localhost:8086/callback`）
- Refresh token 保存至 `~/.ads-skill/tokens.json`（权限 0600）
- 使用 `prompt=consent` 强制显示授权页，确保每次都能获得 refresh token

**常见错误：**

| 错误 | 原因 | 解决方法 |
|------|------|----------|
| `redirect_uri_mismatch` | Cloud Console 未添加回调 URI | 在 Cloud Console 添加 `http://localhost:8086/callback` |
| `No refresh token returned` | 未强制显示授权页 | 先撤销授权再重新登录：`ads-skill auth logout && ads-skill auth login` |
| `access_denied` | 用户拒绝授权 | 重新运行 `ads-skill auth login` |

### 查看认证状态

```bash
ads-skill auth status
```

显示：是否已登录、refresh token 是否存在、access token 剩余时间。

### Token 自动刷新机制

- `google-ads` 库在每次 API 调用时自动检测 access token 是否过期
- 过期则使用 refresh token 静默刷新，无需用户介入
- Refresh token 长期有效（除非用户撤销授权或超过 6 个月未使用）
- 手动强制刷新：`ads-skill auth refresh`

### 退出登录

```bash
ads-skill auth logout
```

删除 `~/.ads-skill/tokens.json`，下次需重新 `auth login`。

---

## 账户查看

### 列出所有账户

```bash
ads-skill accounts
ads-skill accounts --mcc <MCC_CUSTOMER_ID>   # 指定 MCC
```

- 自动识别 MCC（管理账户）并展开其下的子客户账户
- 显示账户 ID、名称、类型（MCC/Client）、状态、币种

**注意：** 如果账户是 MCC，campaigns 和 summary 命令必须指定子账户 ID 加 `--mcc` 参数。

---

## 广告数据查看

### 查看 Campaigns（过去 30 天）

```bash
ads-skill campaigns -a <CUSTOMER_ID>
ads-skill campaigns -a <CUSTOMER_ID> --mcc <MCC_ID>
```

展示字段：名称、状态、广告渠道、曝光量、点击量、CTR%、花费、转化数、平均 CPC。

### 查看账户汇总报告

```bash
ads-skill summary -a <CUSTOMER_ID> --days 7
ads-skill summary -a <CUSTOMER_ID> --days 14
ads-skill summary -a <CUSTOMER_ID> --days 30    # 默认
ads-skill summary -a <CUSTOMER_ID> --mcc <MCC_ID> --days 7
```

展示字段：曝光量、点击量、CTR、平均 CPC、总花费、转化数、转化价值、ROAS、CPA、搜索曝光份额。

---

## 典型操作流程

```bash
# 1. 首次使用：配置完凭证后登录
ads-skill auth login

# 2. 查看有哪些账户
ads-skill accounts

# 3. 查看子账户的 campaigns（MCC 场景）
ads-skill campaigns -a 2752299046 --mcc 7153662160

# 4. 查看最近 7 天账户汇总
ads-skill summary -a 2752299046 --mcc 7153662160 --days 7
```

---

## 文件与路径

| 路径 | 说明 |
|------|------|
| `~/.ads-skill/tokens.json` | OAuth tokens（refresh token 长期存储） |
| `ads_skill/config.py` | 凭证配置（CLIENT_ID / SECRET / DEVELOPER_TOKEN） |
| `ads_skill/auth.py` | OAuth2 流程与 token 刷新逻辑 |
| `ads_skill/client.py` | Google Ads API 封装（GAQL 查询） |
| `ads_skill/cli.py` | CLI 命令入口 |

---

## 凭证收集检查清单

在协助用户配置时，按顺序确认以下内容：

- [ ] **Developer Token** — 已填入 `config.py` 或 `ADS_DEVELOPER_TOKEN` 环境变量
- [ ] **Client ID** — 已填入 `config.py` 或 `ADS_CLIENT_ID`，格式为 `*.apps.googleusercontent.com`
- [ ] **Client Secret** — 已填入 `config.py` 或 `ADS_CLIENT_SECRET`，格式为 `GOCSPX-*`
- [ ] **重定向 URI** — Google Cloud Console 中已添加 `http://localhost:8086/callback`
- [ ] **OAuth 登录** — 运行 `ads-skill auth login` 完成授权，`auth status` 确认 refresh token 存在
