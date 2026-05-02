# AI Novel Engine: 黑盒叙事创世引擎 🌌 
AI Novel Engine 是一款专为“零干预”长篇小说生成设计的全自动流水线。它采用全栈架构思维，通过宏观大纲锁死与微观叙事弹性的对冲机制，实现在无人值守的情况下自动产出 20-30 万字、逻辑自洽的双语小说。  

## 核心设计哲学 (The Philosophy) 
1. 黑盒化 (Black-Box Logic): 系统一旦点火，无需人工审阅。通过 PlotEnforcer（裁决者）与 ChapterGenerator（生成者）的对抗，实现自我修正。  
2. 结构化语言映射 (Linguistic Mapping): 彻底解决 LLM 中英混杂的语法灾难。将“对话/心理”绑定为英文，将“旁白/环境”绑定为中文，确保 60% 的英文占比且阅读体验流畅。  
3. 双轨记忆系统 (Dual-Track Memory):
   热记忆 (State Tracker): 实时追踪角色的血条、境界、装备，防止“复活”或“战力崩坏”。  
   冷记忆 (Vector DB): 基于 ChromaDB 的长效伏笔检索。

## 关键特性 (Features)
1. 🚀 双模启动管线: 既拥有可视化的 Streamlit 创世控制台，也支持剥离 UI 的 --headless 后台守护进程模式。  
2. ⚖️ 四维裁决矩阵: 裁决者从剧情锚点、战力边界、状态继承、语言纪律四个维度进行“生死判罚”。  
3. 🛡️ 工业级 API 装甲: 基于 RobustCaller 的指数级退避机制，无惧 429 限流与网络波动。  
4. 💾 断点持久化: 自动封存 checkpoint.json，支持断电后无缝继续生成。

## 快速开始 (Quick Start)
1. 克隆与环境配置
git clone https://github.com/Hogan-Wang1/ai_novel_engine.git
cd ai_novel_engine
pip install -r requirements.txt
2. 注入秘钥 (Security)
复制模板并填入你的 DeepSeek API Key：
cp .env.example .env
编辑 .env，填入你的 OPENAI_API_KEY 和 OPENAI_BASE_URL
3. 点火启动
python main.py
执行后将自动弹出 Web UI。在面板中设定你的“创世法则”，点击“启动”后即可关闭网页，引擎将在后台开始编织世界。  

## 配置文件规范 (run_config.yaml)
你可以通过 UI 动态修改以下核心参数：  
linguistic_mapping: 定义不同叙事块的语言属性。
power_ceiling: 设定绝对的战力天花板（物理锁）。
enforcer_strictness: 调整裁决者的“判罚尺度”。

## 项目结构 (Directory Structure)
``` 
ai_novel_engine/
├── clients/           # API 调用装甲 (RobustCaller)
├── config/            # 提示词模板与世界观约束
├── engine/            # 核心逻辑 (Orchestrator, Enforcer, Assembler)
├── memory/            # 双轨记忆 (StateTracker, VectorDB)
├── output/            # 最终生成的章节 TXT 与断点数据
├── ui_dashboard.py    # Streamlit 创世控制台
└── main.py            # 智能路由点火总线
```
Engine-CoPilot 提示：
本引擎目前已针对 DeepSeek-V4 进行深度优化。上传至 GitHub 后，请确保 .env 已被加入 .gitignore 以防止资产泄露。