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
