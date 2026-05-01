import streamlit as st
import yaml
import os

# 定义配置文件路径
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "run_config.yaml")

def load_config():
    """加载 YAML 配置"""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}

def save_config(config_data):
    """保存回 YAML"""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config_data, f, allow_unicode=True, sort_keys=False)
    st.toast("✅ 创世法则已同步至引擎核心！", icon="💾")

# ================= UI 页面构建 =================
st.set_page_config(page_title="AI Novel Engine | 创世控制台", layout="wide")

st.title("🌌 AI Novel Engine: 黑盒叙事创世面板")
st.markdown("通过此面板配置**结构化双语映射**与**世界观边界框**，引擎将严格遵循此法则执行无人值守生成。")

# 加载当前配置
config = load_config()
if not config:
    st.error("未找到 run_config.yaml 文件，请检查路径。")
    st.stop()

# 使用 Tabs 分区，避免页面过于拥挤
tab1, tab2, tab3, tab4 = st.tabs(["📚 宏观设定 (Meta)", "🗣️ 语言结构映射 (Linguistics)", "⚔️ 世界观边界锁 (Bounding Box)", "⚙️ 引擎调优 (Engine)"])

with tab1:
    st.header("小说基础元数据")
    col1, col2 = st.columns(2)
    with col1:
        config['project_meta']['title'] = st.text_input("书名 (Title)", config['project_meta'].get('title', ''))
        config['project_meta']['target_word_count'] = st.number_input("目标总字数", value=config['project_meta'].get('target_word_count', 250000), step=10000)
    with col2:
        config['project_meta']['total_volumes'] = st.number_input("规划卷数", value=config['project_meta'].get('total_volumes', 4), min_value=1)
        config['project_meta']['chapters_per_volume'] = st.number_input("每卷章节数", value=config['project_meta'].get('chapters_per_volume', 25), min_value=1)
    
    config['project_meta']['pov'] = st.selectbox("核心叙事视角 (POV)", 
        ["Third-Person Limited (第三人称限制视角)", "First-Person (第一人称视角)", "Omniscient (上帝视角)"], 
        index=0)

with tab2:
    st.header("结构化语言配比")
    st.info("💡 将语言与叙事块绑定，从根本上解决 LLM 的中英混杂语法问题。")
    config['linguistic_mapping']['narration_language'] = st.text_input("旁白/环境描写语言", config['linguistic_mapping'].get('narration_language', ''))
    config['linguistic_mapping']['dialogue_language'] = st.text_area("角色对话语言 (重点约束)", config['linguistic_mapping'].get('dialogue_language', ''))
    config['linguistic_mapping']['lore_terms_language'] = st.text_input("专有名词语言", config['linguistic_mapping'].get('lore_terms_language', ''))

with tab3:
    st.header("战力与逻辑防崩塌系统")
    config['world_bounding_box']['global_tone'] = st.text_input("全局基调 (Global Tone)", config['world_bounding_box'].get('global_tone', ''))
    config['world_bounding_box']['power_ceiling'] = st.text_area("战力天花板 (Power Ceiling) - 必须极其具体", config['world_bounding_box'].get('power_ceiling', ''))
    
    st.subheader("禁忌词库 (Banned Words)")
    banned_words_str = st.text_area("输入违禁词（用逗号分隔）", ", ".join(config['world_bounding_box'].get('banned_words', [])))
    config['world_bounding_box']['banned_words'] = [w.strip() for w in banned_words_str.split(",") if w.strip()]

with tab4:
    st.header("引擎黑盒参数")
    config['engine_parameters']['enforcer_strictness'] = st.slider("大纲裁决者严苛度 (Enforcer Strictness)", 0.0, 1.0, config['engine_parameters'].get('enforcer_strictness', 0.8), 0.05)
    config['engine_parameters']['max_retries_per_chapter'] = st.number_input("崩坏重试上限 (Max Retries)", value=config['engine_parameters'].get('max_retries_per_chapter', 3), min_value=1)

# ================= 侧边栏与执行控制 =================
with st.sidebar:
    st.image("https://api.dicebear.com/7.x/bottts/svg?seed=novelEngine", width=150)
    st.markdown("### 引擎控制 (Engine Control)")
    
    if st.button("💾 保存法则 (Save Config)", use_container_width=True, type="primary"):
        save_config(config)
        
    st.divider()
    st.warning("⚠️ 启动前请确保法则已保存")
    
    if st.button("🚀 启动百万字无人值守管线", use_container_width=True):
        st.success("流水线启动指令已下达！引擎正在接管上下文...")
        # 此处可以调用你的 orchestrator 启动脚本
        # import subprocess
        # subprocess.Popen(["python", "main.py"])