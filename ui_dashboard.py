import streamlit as st
import yaml
import os
import sys
import subprocess

# ================= 绝对路径锚定 (Path Anchoring) =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(BASE_DIR, "config")
CONFIG_PATH = os.path.join(CONFIG_DIR, "run_config.yaml")

def init_default_config() -> dict:
    """自动初始化默认法则，防止冷启动崩溃"""
    default_config = {
        "project_meta": {
            "title": "Neon Rain: Cyberpunk Genesis",
            "target_word_count": 250000,
            "total_volumes": 4,
            "chapters_per_volume": 25,
            "pov": "Third-Person Limited"
        },
        "linguistic_mapping": {
            "narration_language": "Chinese (Cold, minimalist noir style)",
            "dialogue_language": "English (Colloquial, 60% of total text)",
            "lore_terms_language": "English (Capitalized)"
        },
        "world_bounding_box": {
            "global_tone": "Cyberpunk / Tech-Noir",
            "power_ceiling": "Street level. No superpowers, only cybernetics.",
            "banned_words": ["恐怖如斯", "倒吸一口凉气", "眼中闪过精光"],
            "forbidden_tropes": ["Deus ex machina", "System panels"]
        },
        "engine_parameters": {
            "enforcer_strictness": 0.85,
            "max_retries_per_chapter": 3
        }
    }
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(default_config, f, allow_unicode=True, sort_keys=False)
    return default_config

def load_config() -> dict:
    """安全加载配置文件"""
    if not os.path.exists(CONFIG_PATH):
        return init_default_config()
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def save_config(config_data: dict):
    """持久化用户自定义法则[cite: 3]"""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config_data, f, allow_unicode=True, sort_keys=False)
    st.toast("✅ 创世法则已同步至引擎核心！", icon="💾")

# ================= UI 页面构建 (The Genesis Console) =================
st.set_page_config(page_title="Engine-CoPilot | 创世面板", layout="wide")

st.title("🌌 AI Novel Engine: 黑盒叙事创世面板")
st.markdown("---")

config = load_config()

# 布局分区
tab_meta, tab_ling, tab_box, tab_engine = st.tabs([
    "📚 宏观设定 (Meta)", 
    "🗣️ 语言映射 (Linguistics)", 
    "⚔️ 世界观边界 (Bounding Box)", 
    "⚙️ 引擎调优 (Engine)"
])

with tab_meta:
    col1, col2 = st.columns(2)
    with col1:
        config['project_meta']['title'] = st.text_input("小说标题", config['project_meta']['title'])
        config['project_meta']['target_word_count'] = st.number_input("目标字数", value=config['project_meta']['target_word_count'], step=10000)
    with col2:
        config['project_meta']['total_volumes'] = st.number_input("规划卷数", value=config['project_meta']['total_volumes'], min_value=1)
        config['project_meta']['chapters_per_volume'] = st.number_input("每卷章节", value=config['project_meta']['chapters_per_volume'], min_value=1)
    config['project_meta']['pov'] = st.selectbox("视角 (POV)", ["Third-Person Limited", "First-Person", "Omniscient"])

with tab_ling:
    st.info("💡 结构化语言绑定：强制模型在特定叙事块切换语言，确保 60% 英文占比[cite: 3]。")
    config['linguistic_mapping']['narration_language'] = st.text_input("旁白语言 (Narration)", config['linguistic_mapping']['narration_language'])
    config['linguistic_mapping']['dialogue_language'] = st.text_area("对话语言 (Dialogue)", config['linguistic_mapping']['dialogue_language'])
    config['linguistic_mapping']['lore_terms_language'] = st.text_input("专有名词 (Lore)", config['linguistic_mapping']['lore_terms_language'])

with tab_box:
    config['world_bounding_box']['global_tone'] = st.text_input("全局基调", config['world_bounding_box']['global_tone'])
    config['world_bounding_box']['power_ceiling'] = st.text_area("战力天花板", config['world_bounding_box']['power_ceiling'])
    
    banned_str = st.text_area("违禁词库 (用逗号分隔)", ", ".join(config['world_bounding_box']['banned_words']))
    config['world_bounding_box']['banned_words'] = [w.strip() for w in banned_str.split(",") if w.strip()]

with tab_engine:
    config['engine_parameters']['enforcer_strictness'] = st.slider("裁决者严苛度", 0.0, 1.0, config['engine_parameters']['enforcer_strictness'])
    config['engine_parameters']['max_retries_per_chapter'] = st.number_input("单章最大重试次数", value=config['engine_parameters']['max_retries_per_chapter'], min_value=1)

# ================= 侧边栏控制 (Execution Control) =================
with st.sidebar:
    st.image(f"https://api.dicebear.com/7.x/bottts/svg?seed={config['project_meta']['title']}", width=150)
    st.header("引擎指令中枢")
    
    if st.button("💾 保存创世法则", use_container_width=True, type="primary"):
        save_config(config)
        
    st.divider()
    
    if st.button("🚀 启动无人值守管线", use_container_width=True):
        st.success("🔥 引擎点火成功！")
        st.info("后台正在执行 DeepSeek-V4 大纲推演。你可以关闭此页面，在 logs/engine_run.log 查看进度[cite: 3]。")
        
        # 异步启动无头模式进程[cite: 3]
        main_script = os.path.join(BASE_DIR, "main.py")
        subprocess.Popen([sys.executable, main_script, "--headless"])