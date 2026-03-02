# workflow-automation

个人自动化项目，包含业务跟进、产品发布、文案生成、视频处理四个模块。

## 快速开始
1. 安装依赖：`pip install -r requirements.txt`
2. 配置：复制 `config/*.yaml.example` 为 `*.yaml` 并填写
3. 运行测试：`pytest tests/`

## 目录结构
workflow-automation/                  # 项目根目录
├── README.md                         # 项目总说明：目标、模块、快速开始
├── .gitignore                        # 忽略临时文件、日志、密钥等
├── requirements.txt                   # Python 依赖库列表
├── Makefile                           # 可选，简化常用命令（如安装、测试）
│
├── config/                            # 配置文件（所有敏感信息和平台特定配置）
│   ── templates/                       # 文案模板
│
├── src/                                # 源代码主目录（模块化组织）
│   ├── __init__.py                      # 使 src 成为 Python 包
│   │
│   ├── business_followup/               # 模块1：业务跟进自动化
│   │   ├── __init__.py
│   │
│   ├── product_publish/                  # 模块2：产品发布自动化
│   │   ├── __init__.py
│   │
│   ├── content_generation/                # 模块3：文案生成自动化
│   │   ├── __init__.py
│   │
│   ├── video_processing/                   # 模块4：视频处理自动化
│   │   ├── __init__.py
│   │
│   └── utils/                              # 通用工具模块
│       ├── __init__.py
│
├── scripts/                              # 可执行脚本（供命令行调用或定时任务）
│
├── tests/                                 # 单元测试和集成测试
│   ├── __init__.py
│   └── fixtures/                            # 测试数据
│   
├── docs/                                    # 项目文档
│   ├── setup.md                             # 安装和配置指南
│   ├── api_reference.md                      # 内部模块 API 说明
│   ├── workflow_diagrams/                    # 流程图（Mermaid 或图片）
│   └── troubleshooting.md                    # 常见问题解决
│
└── .github/                                 # GitHub 专用目录



