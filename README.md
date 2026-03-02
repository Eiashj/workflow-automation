# workflow-automation

个人自动化项目，包含业务跟进、产品发布、文案生成、视频处理四个模块。

## 快速开始
1. 安装依赖：`pip install -r requirements.txt`
2. 配置：复制 `config/*.yaml.example` 为 `*.yaml` 并填写
3. 运行测试：`pytest tests/`

## 目录结构
```text
workflow-automation/
├── README.md                 # 项目总说明
├── requirements.txt          # Python 依赖
├── Makefile                  # 常用命令
├── config/                   # 配置文件
├── templates/                # 文案模板
├── src/                      # 源代码主目录
│   ├── __init__.py
│   ├── business_followup/    # 模块1：业务跟进
│   │   └── __init__.py
│   ├── product_publish/      # 模块2：产品发布
│   │   └── __init__.py
│   ├── content_generation/   # 模块3：文案生成
│   │   └── __init__.py
│   ├── video_processing/     # 模块4：视频处理
│   │   └── __init__.py
│   └── utils/                # 通用工具
│       └── __init__.py
├── scripts/                  # 可执行脚本
├── tests/                    # 测试
│   └── fixtures/             # 测试数据
└── docs/                     # 项目文档
    ├── setup.md
    ├── api_reference.md
    ├── workflow_diagrams/
    └── troubleshooting.md
```
