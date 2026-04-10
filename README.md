# Sanction Checker (Suppliers & Shareholders)

一个更轻量的本地网页程序：上传 Excel（首列名称），自动与以下名单进行模糊匹配：
- OFAC SDN
- 联合国安理会综合制裁名单
- 欧盟制裁名单
- PPATK（通过 `data/ppatk_manual.xlsx` 手工维护）

## 功能
- Web 页面上传并执行查询
- 自动输出 Excel 查询结果（含匹配分数/来源/匹配名称）
- 自动生成每条查询结果截图（PNG）并打包为 ZIP 下载
- 本地目录分离：上传文件、Excel、截图压缩包分别存储

## 运行
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

访问：`http://127.0.0.1:5000`

## 数据说明
首次运行会自动下载：
- OFAC SDN csv
- UN consolidated xml
- EU sanctions csv

PPATK 没有稳定公开结构化下载接口，程序采用可选手工导入：
- 新建 `data/ppatk_manual.xlsx`
- 首列填名称

## 判定阈值（可调）
- `>= 92`：命中（是）
- `80~91.99`：待复核
- `< 80`：否

> 说明：模糊匹配仅用于初筛，命中项应人工复核后再做合规决策。


## 常见问题
- 出现 `Internal Server Error`：通常是依赖未安装或名单下载失败。
  1) 先执行 `pip install -r requirements.txt`
  2) 检查网络是否可访问 OFAC/UN/EU 源站
  3) 如网络受限，可手工把 `ofac_sdn.csv`、`un_consolidated.xml`、`eu_fsf.csv` 放到 `data/` 目录


## 初版常见根因（会导致“无法分析输出”）
- **数据源不可达/被网关替换为 HTML**：初版会把非 CSV/XML 内容当作名单文件解析，导致结果异常或全量“未命中”。
- **EU 下载链接可能失效**：令牌型链接若返回非结构化内容，会导致 EU 数据为空。
- **名单数量异常未提示**：初版不会显示各数据源加载条数，用户难以判断是不是“没连上数据源”。

当前版本已增加：
1) 下载内容格式校验；
2) 各名单条数展示；
3) `TOTAL < 1000` 时阻止分析并提示先修复数据源。
