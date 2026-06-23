# CatsAPI Key 配置引导

## 何时读这个文件

- 用户首次使用 catsapi skill
- `--check` 返回 401 / 403
- 用户主动问"怎么配置 API Key?"、"去哪拿 Key?"

## 引导流程

按以下话术引导用户,**每一步都等用户回应后再进行下一步**:

### Step 1: 确认是否已有账号

> 用 catsapi 前需要先在 [catsapi.com](https://catsapi.com) 注册,用 LinuxDo OAuth 登录或邮箱注册都行。已经注册好了吗?🐱

### Step 2: 指引生成 API Key

> 登录后点左边栏的"**API Key**"页面,如果没有就点"**创建 API Key**" 按钮。拿到一串 `cats-` 开头的 Key 就对啦~

### Step 3: 让用户设置环境变量

> 把拿到的 Key 复制好,然后在终端跑:
>
> ```bash
> export CATSAPI_API_KEY=cats-你复制的Key
> ```
>
> 想永久生效就写进 `~/.zshrc`、`~/.bashrc`、项目 `.env` 或 `~/.catsapi.env` 里。不要把 Key 发到聊天里,告诉我设置好了,我来帮你自检一下~

### Step 4: 自检

用户说设置好了后:

```bash
python3 {baseDir}/scripts/catsapi.py --check
```

成功会输出 `{"balance": N}`,告诉用户:
"API Key 搞定啦~ 目前余额 **N 猫币**,可以开始画图/生视频了!"

失败(401/403):
"Key 看起来没生效,可能是配置没有被当前进程读取、Key 被截断,或者 Key 被重置了。请重新复制完整 Key 后保存,我再帮你用 `--check` 自检。不要把 Key 发到聊天里。"

## 常见问题

### Q: "猫币从哪来?"
A: catsapi.com → 兑换码页面用兑换码兑换;新用户注册/LinuxDo 登录通常有赠送。

### Q: "重置了 Key 能重置回来吗?"
A: 不能。每天可重置一次,旧 Key 会立即失效。让用户去页面重新创建并更新环境变量。

### Q: "本地部署怎么办?"
A: 让用户设 `CATSAPI_BASE=http://localhost:8000`(或他们自建域名),Key 还是他后端数据库里的那个。
