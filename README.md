# AHarbitrage Response

企业微信 AH 溢价监控回调服务，接收用户在企业微信应用中的消息指令并执行对应业务操作。

## 前置条件

部署前需在 `AH_LOG_ROOT` 指向的目录下准备好三个 CSV 文件：

```
{AH_LOG_ROOT}/
└── config/
    ├── ah_alarmRate.csv   # 溢价监控阈值（列: a_stock_code, a_name, ah_low, ah_high）
    ├── alert_state.csv    # 告警状态（列: a_stock_code, last_state）
    └── ah_stock_map.csv   # A/H 股映射（列: a_stock_code, h_stock_code, stock_name, in_or_out, ...）
```

## Docker 启动

```bash
# 在 AHarbitrage_response 目录下
docker build -t aharbitrage-response .

# 启动（将 CSV 数据目录挂载到容器内 /app/data）
docker run -d --name aharbitrage-response -p 5000:5000 -v /你的数据目录:/app/data aharbitrage-response
```

启动后在[企业微信管理后台](https://work.weixin.qq.com) → 应用管理 → 自建应用 → 接收消息 → 设置回调 URL 为 `http://你的服务器IP:5000/callback`。

## 指令说明

在企业微信应用中向机器人发送以下指令：

### 1. 更新溢价告警阈值

```
000333,0.03,0.09
```

- 格式：`A股代码,溢价下限,溢价上限`
- 已在 `ah_alarmRate.csv` 中则更新，不在则从股票映射表查名称后新增
- 同步重置告警状态为 normal
- 返回：全量阈值表内容

### 2. 查询 A/H 股价及溢价率

```
000333
```

- 格式：`6位A股代码`
- 多线程拉取腾讯财经 A 股 + H 股实时行情
- 根据 `AH_EXCHG_RATE` 汇率换算港元并计算溢价率
- 返回：股票名称、A 股价格、H 股价格、A/H 溢价率

### 3. 查看溢价监控列表

```
提示列表
```

- 以 `提示` 开头的任意内容均可
- 返回：`ah_alarmRate.csv` 全部内容

### 4. 查看监控股票列表

```
监控列表
```

- 以 `监控` 开头的任意内容均可
- 返回：`ah_stock_map.csv` 中所有 `in_or_out=1` 的股票名称，每行一个

### 5. 加入/移出监控列表

```
000333,1
000333,0
```

- 格式：`A股代码,1`（加入）或 `A股代码,0`（移出）
- 修改 `ah_stock_map.csv` 中对应行的 `in_or_out` 列
- 返回：当前所有监控中的股票名称

### 6. 查看帮助

```
help
```

支持 `help`、`帮助`、`?`、`？`。

## 汇率自动更新

服务启动时会立即拉取一次上交所港股通参考汇率，之后每个工作日 9:24 自动更新，存入环境变量 `AH_EXCHG_RATE`。查询股价时用该汇率将港元换算为人民币计算溢价率。

## 日志

日志异步写入文件，不输出控制台：

```
{AH_LOG_ROOT}/log/response/{YYYYMMDD}/AHarbitrage_response_{YYYYMMDD}.log
```

## 文件结构

```
AHarbitrage_response/
├── Dockerfile
├── README.md
├── requirements.txt
├── bot.py                  # Flask 回调服务 + 模块加载时启动 scheduler
├── handler.py              # 业务指令处理
├── scheduler.py            # 每日 9:24 拉取汇率
├── sse_reference_rate.py   # 上交所爬取港股通参考汇率
├── wecom_alert.py          # 企业微信消息发送（token 缓存 + 过期重试）
├── WXBizMsgCrypt.py        # 企业微信加解密
└── logger.py               # 异步文件日志
```
