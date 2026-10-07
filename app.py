import uuid

import streamlit as st

from core.jobs import create_job
from core.github_jobs import create_github_job


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Auto Faceless Studio",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# PREMIUM UI
# ============================================================

st.markdown(
    """
    <style>

    /* ======================================================
       GLOBAL
       ====================================================== */

    .stApp {
        background:
            radial-gradient(
                circle at 15% 10%,
                rgba(94, 72, 255, 0.18),
                transparent 30%
            ),
            radial-gradient(
                circle at 85% 15%,
                rgba(0, 214, 255, 0.12),
                transparent 28%
            ),
            radial-gradient(
                circle at 50% 90%,
                rgba(168, 85, 247, 0.10),
                transparent 32%
            ),
            #070910;
        color: #f5f7ff;
    }

    .main .block-container {
        max-width: 1250px;
        padding-top: 2rem;
        padding-bottom: 4rem;
    }

    /* ======================================================
       SIDEBAR
       ====================================================== */

    section[data-testid="stSidebar"] {
        background:
            linear-gradient(
                180deg,
                rgba(13, 17, 30, 0.98),
                rgba(7, 9, 16, 0.98)
            );
        border-right: 1px solid rgba(255,255,255,0.07);
    }

    section[data-testid="stSidebar"] > div {
        padding-top: 1.5rem;
    }

    /* ======================================================
       TEXT
       ====================================================== */

    h1,
    h2,
    h3 {
        color: #f8f9ff !important;
        letter-spacing: -0.025em;
    }

    p,
    label,
    .stMarkdown {
        color: #c8ccda;
    }

    /* ======================================================
       HERO
       ====================================================== */

    .hero {
        position: relative;
        overflow: hidden;
        padding: 34px 36px;
        margin-bottom: 25px;
        border-radius: 24px;
        border: 1px solid rgba(255,255,255,0.09);
        background:
            linear-gradient(
                135deg,
                rgba(26, 31, 55, 0.96),
                rgba(12, 16, 29, 0.96)
            );
        box-shadow:
            0 25px 80px rgba(0,0,0,0.32),
            inset 0 1px 0 rgba(255,255,255,0.04);
    }

    .hero:before {
        content: "";
        position: absolute;
        width: 260px;
        height: 260px;
        right: -100px;
        top: -130px;
        background: rgba(93, 73, 255, 0.22);
        filter: blur(70px);
        border-radius: 50%;
    }

    .hero-title {
        font-size: 42px;
        font-weight: 800;
        line-height: 1.05;
        margin-bottom: 12px;
        color: #ffffff;
    }

    .hero-title span {
        background: linear-gradient(
            90deg,
            #8b7cff,
            #38d9ff
        );
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .hero-subtitle {
        color: #aeb5c9;
        font-size: 16px;
        max-width: 760px;
        line-height: 1.6;
    }

    .hero-badges {
        display: flex;
        flex-wrap: wrap;
        gap: 9px;
        margin-top: 20px;
    }

    .badge {
        padding: 7px 12px;
        border-radius: 999px;
        background: rgba(255,255,255,0.055);
        border: 1px solid rgba(255,255,255,0.08);
        color: #d9dded;
        font-size: 12px;
        font-weight: 600;
    }

    /* ======================================================
       CARDS
       ====================================================== */

    .glass-card {
        padding: 22px;
        border-radius: 20px;
        background: rgba(15, 19, 33, 0.78);
        border: 1px solid rgba(255,255,255,0.075);
        box-shadow:
            0 16px 45px rgba(0,0,0,0.20),
            inset 0 1px 0 rgba(255,255,255,0.025);
        margin-bottom: 18px;
    }

    .card-title {
        font-size: 18px;
        font-weight: 750;
        color: #f6f7ff;
        margin-bottom: 5px;
    }

    .card-description {
        font-size: 13px;
        color: #8f97ad;
        margin-bottom: 18px;
    }

    /* ======================================================
       SECTION LABEL
       ====================================================== */

    .section-label {
        display: flex;
        align-items: center;
        gap: 9px;
        margin: 28px 0 13px 2px;
        font-size: 13px;
        font-weight: 750;
        text-transform: uppercase;
        letter-spacing: 0.09em;
        color: #8992aa;
    }

    /* ======================================================
       INPUTS
       ====================================================== */

    div[data-baseweb="input"] > div,
    div[data-baseweb="select"] > div,
    div[data-baseweb="textarea"] > div {
        background: rgba(255,255,255,0.035) !important;
        border-color: rgba(255,255,255,0.09) !important;
        border-radius: 12px !important;
    }

    input,
    textarea {
        color: #f4f6ff !important;
    }

    /* ======================================================
       BUTTON
       ====================================================== */

    .stButton > button {
        border-radius: 12px;
        border: 1px solid rgba(255,255,255,0.09);
        background: rgba(255,255,255,0.045);
        color: #e9ecf8;
        font-weight: 650;
        min-height: 44px;
        transition: all 0.2s ease;
    }

    .stButton > button:hover {
        border-color: rgba(120,110,255,0.55);
        background: rgba(100,90,255,0.13);
        transform: translateY(-1px);
    }

    /* ======================================================
       PRIMARY BUTTON
       ====================================================== */

    .primary-wrap button {
        background:
            linear-gradient(
                100deg,
                #6957ff,
                #3dbfff
            ) !important;
        border: none !important;
        color: white !important;
        font-size: 16px !important;
        font-weight: 800 !important;
        min-height: 54px !important;
        box-shadow:
            0 12px 35px rgba(85, 100, 255, 0.28);
    }

    .primary-wrap button:hover {
        filter: brightness(1.08);
        transform: translateY(-2px);
    }

    /* ======================================================
       RADIO
       ====================================================== */

    div[role="radiogroup"] {
        gap: 7px;
    }

    /* ======================================================
       EXPANDER
       ====================================================== */

    details {
        background: rgba(255,255,255,0.025);
        border: 1px solid rgba(255,255,255,0.07);
        border-radius: 14px;
    }

    /* ======================================================
       STATUS
       ====================================================== */

    .status-card {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 17px 19px;
        border-radius: 16px;
        background: rgba(255,255,255,0.035);
        border: 1px solid rgba(255,255,255,0.07);
        margin-bottom: 10px;
    }

    .status-left {
        display: flex;
        align-items: center;
        gap: 12px;
    }

    .status-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        background: #49e38d;
        box-shadow: 0 0 15px rgba(73,227,141,0.55);
    }

    .status-text {
        color: #e7eaf5;
        font-weight: 650;
    }

    .status-small {
        color: #80889e;
        font-size: 12px;
    }

    /* ======================================================
       FOOTER
       ====================================================== */

    .footer {
        text-align: center;
        color: #596177;
        font-size: 12px;
        padding-top: 25px;
    }

    /* ======================================================
       MOBILE
       ====================================================== */

    @media (max-width: 768px) {

        .main .block-container {
            padding-left: 1rem;
            padding-right: 1rem;
        }

        .hero {
            padding: 25px 22px;
            border-radius: 19px;
        }

        .hero-title {
            font-size: 30px;
        }

        .hero-subtitle {
            font-size: 14px;
        }

    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# HERO
# ============================================================

st.markdown(
    """
    <div class="hero">
        <div class="hero-title">
            Auto Faceless <span>Studio</span>
        </div>

        <div class="hero-subtitle">
            Turn a YouTube reference, topic or idea into a structured,
            high-retention faceless short using the Pro V2 pipeline.
        </div>

        <div class="hero-badges">
            <div class="badge">⚡ Smart Research</div>
            <div class="badge">🎯 Hook Detection</div>
            <div class="badge">🧠 Story Reconstruction</div>
            <div class="badge">🎬 Dynamic Editing</div>
            <div class="badge">💬 Viral Captions</div>
            <div class="badge">📱 9:16 Output</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown(
        """
        <div style="
            font-size:22px;
            font-weight:800;
            color:#f5f7ff;
            margin-bottom:4px;
        ">
            🎬 Pro Controls
        </div>

        <div style="
            color:#777f96;
            font-size:12px;
            margin-bottom:22px;
        ">
            V2 generation settings
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --------------------------------------------------------
    # DURATION
    # --------------------------------------------------------

    st.markdown("**⏱ Duration**")

    duration_choice = st.selectbox(
        "Video Duration",
        [
            "10 sec",
            "15 sec",
            "20 sec",
            "30 sec",
            "45 sec",
            "60 sec",
            "Custom",
        ],
        index=3,
        label_visibility="collapsed",
    )

    duration_map = {
        "10 sec": 10,
        "15 sec": 15,
        "20 sec": 20,
        "30 sec": 30,
        "45 sec": 45,
        "60 sec": 60,
    }

    if duration_choice == "Custom":
        duration = st.slider(
            "Custom Duration",
            5,
            180,
            30,
            1,
        )
    else:
        duration = duration_map[duration_choice]

    st.divider()

    # --------------------------------------------------------
    # CAPTIONS
    # --------------------------------------------------------

    st.markdown("**💬 Captions**")

    caption_style = st.selectbox(
        "Caption Style",
        [
            "Bold Viral",
            "Karaoke",
            "Clean",
            "Impact",
            "MrBeast-style",
            "Minimal Bottom",
            "Custom",
        ],
        index=0,
    )

    caption_size = st.slider(
        "Font Size",
        18,
        100,
        52,
        2,
    )

    caption_position = st.selectbox(
        "Position",
        [
            "Bottom",
            "Lower Third",
            "Center",
            "Upper Third",
            "Top",
        ],
        index=0,
    )

    caption_words_per_line = st.slider(
        "Words / Line",
        1,
        8,
        4,
    )

    caption_max_lines = st.slider(
        "Maximum Lines",
        1,
        3,
        2,
    )

    keyword_emphasis = st.checkbox(
        "Keyword Emphasis",
        True,
    )

    caption_stroke = st.checkbox(
        "Stroke",
        True,
    )

    caption_shadow = st.checkbox(
        "Shadow",
        True,
    )

    caption_box = st.checkbox(
        "Background Box",
        False,
    )

    st.divider()

    # --------------------------------------------------------
    # EDITING
    # --------------------------------------------------------

    st.markdown("**🎬 Editing**")

    dynamic_zoom = st.checkbox(
        "Dynamic Punch-In / Zoom",
        True,
    )

    remove_silence = st.checkbox(
        "Remove Dead Space",
        True,
    )

    normalize_audio = st.checkbox(
        "Audio Normalization",
        True,
    )

    visual_changes = st.selectbox(
        "Visual Rhythm",
        [
            "Dynamic",
            "Fast",
            "Balanced",
            "Slow",
        ],
        index=0,
    )


# ============================================================
# MAIN WORKSPACE
# ============================================================

st.markdown(
    '<div class="section-label">🚀 CREATE NEW VIDEO</div>',
    unsafe_allow_html=True,
)


# ============================================================
# INPUT CARD
# ============================================================

st.markdown(
    """
    <div class="glass-card">
        <div class="card-title">Choose Your Source</div>
        <div class="card-description">
            Give V2 a reference video or an idea. The pipeline will
            analyze the context and build the strongest possible story.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


input_mode = st.radio(
    "Input Type",
    [
        "YouTube URL",
        "Topic",
        "Idea",
        "Keyword",
    ],
    horizontal=True,
    label_visibility="collapsed",
)


if input_mode == "YouTube URL":

    source_value = st.text_input(
        "YouTube URL",
        placeholder="https://www.youtube.com/watch?v=...",
        label_visibility="collapsed",
    )

    st.caption(
        "🔗 Reference mode — V2 researches/analyzes the source before rebuilding the story."
    )

else:

    source_value = st.text_input(
        input_mode,
        placeholder=f"Enter your {input_mode.lower()}...",
        label_visibility="collapsed",
    )

    st.caption(
        "🔎 Research mode — V2 searches related sources and identifies useful footage."
    )


# ============================================================
# ADVANCED SETTINGS
# ============================================================

with st.expander("🧠 Advanced V2 Intelligence"):

    col1, col2 = st.columns(2)

    with col1:

        language = st.selectbox(
            "Language",
            [
                "English",
                "Auto Detect",
            ],
            index=0,
        )

        max_clips = st.slider(
            "Maximum Story Segments",
            3,
            20,
            10,
        )

    with col2:

        research_enabled = st.checkbox(
            "Multi-source Research",
            True,
        )

        contextual_broll = st.checkbox(
            "Contextual B-roll",
            True,
        )

        reaction_selection = st.checkbox(
            "Reaction / Payoff Detection",
            True,
        )


# ============================================================
# SETTINGS OBJECTS
# ============================================================

caption_settings = {
    "style": caption_style,
    "font_size": caption_size,
    "position": caption_position,
    "words_per_line": caption_words_per_line,
    "max_lines": caption_max_lines,
    "keyword_emphasis": keyword_emphasis,
    "stroke": caption_stroke,
    "shadow": caption_shadow,
    "box": caption_box,
}


editing_settings = {
    "dynamic_zoom": dynamic_zoom,
    "remove_silence": remove_silence,
    "normalize_audio": normalize_audio,
    "visual_change_rhythm": visual_changes,
    "research_enabled": research_enabled,
    "contextual_broll": contextual_broll,
    "reaction_selection": reaction_selection,
    "max_clips": max_clips,
    "language": language,
}


# ============================================================
# GENERATE BUTTON
# ============================================================

st.markdown(
    "<br>",
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="primary-wrap">',
    unsafe_allow_html=True,
)

generate = st.button(
    "✨  CREATE PRO V2 VIDEO",
    type="primary",
    use_container_width=True,
)

st.markdown(
    "</div>",
    unsafe_allow_html=True,
)


# ============================================================
# JOB CREATION
# ============================================================

if generate:

    if not source_value.strip():

        st.error(
            "Please enter a YouTube URL, topic, idea or keyword."
        )

    else:

        try:

            # ------------------------------------------------
            # GITHUB TOKEN
            # ------------------------------------------------

            try:
                github_token = st.secrets["GITHUB_TOKEN"]
            except Exception:
                github_token = ""

            if not github_token:
                st.error(
                    "GITHUB_TOKEN is missing from Streamlit Secrets."
                )
                st.stop()

            # ------------------------------------------------
            # INPUT TYPE
            # ------------------------------------------------

            # IMPORTANT:
            # A YouTube URL must enter the V2 video-processing
            # pipeline, NOT the old download-only path.
            if input_mode == "YouTube URL":
                job_type = "video"
            else:
                job_type = "topic"

            # ------------------------------------------------
            # CREATE JOB
            # ------------------------------------------------

            job_id = uuid.uuid4().hex

            job = create_job(
                job_id=job_id,
                job_type=job_type,
                input_value=source_value.strip(),
                duration=duration,
                caption_style=caption_style,
                caption_settings=caption_settings,
                editing_settings=editing_settings,
            )

            # ------------------------------------------------
            # SEND TO GITHUB
            # ------------------------------------------------

            with st.spinner(
                "🚀 Sending Pro V2 job to worker..."
            ):

                github_result = create_github_job(
                    token=github_token,
                    job=job.to_dict(),
                )

            # ------------------------------------------------
            # SUCCESS
            # ------------------------------------------------

            st.success(
                "✅ Pro V2 job successfully queued."
            )

            st.markdown(
                f"""
                <div class="status-card">
                    <div class="status-left">
                        <div class="status-dot"></div>

                        <div>
                            <div class="status-text">
                                V2 Worker Queue
                            </div>

                            <div class="status-small">
                                Job {job_id}
                            </div>
                        </div>
                    </div>

                    <div class="status-small">
                        QUEUED
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.code(
                job_id,
                language="text",
            )

            if github_result:
                st.caption(
                    f"📦 GitHub job created: `{github_result}`"
                )

            st.info(
                "Worker will detect the queued job and run the "
                "V2 research → analysis → story → rendering pipeline."
            )

        except Exception as exc:

            st.error(
                f"❌ Job creation failed: {exc}"
            )


# ============================================================
# LIVE CONFIGURATION PREVIEW
# ============================================================

st.markdown(
    '<div class="section-label">⚙️ CURRENT CONFIGURATION</div>',
    unsafe_allow_html=True,
)

col1, col2, col3, col4 = st.columns(4)


with col1:

    st.markdown(
        f"""
        <div class="glass-card">
            <div style="
                font-size:12px;
                color:#777f96;
            ">
                DURATION
            </div>

            <div style="
                font-size:25px;
                font-weight:800;
                color:#f4f6ff;
                margin-top:5px;
            ">
                {duration}s
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


with col2:

    st.markdown(
        f"""
        <div class="glass-card">
            <div style="
                font-size:12px;
                color:#777f96;
            ">
                CAPTION
            </div>

            <div style="
                font-size:18px;
                font-weight:800;
                color:#f4f6ff;
                margin-top:8px;
            ">
                {caption_style}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


with col3:

    st.markdown(
        f"""
        <div class="glass-card">
            <div style="
                font-size:12px;
                color:#777f96;
            ">
                VISUAL RHYTHM
            </div>

            <div style="
                font-size:18px;
                font-weight:800;
                color:#f4f6ff;
                margin-top:8px;
            ">
                {visual_changes}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


with col4:

    research_status = "ON" if research_enabled else "OFF"

    st.markdown(
        f"""
        <div class="glass-card">
            <div style="
                font-size:12px;
                color:#777f96;
            ">
                RESEARCH
            </div>

            <div style="
                font-size:18px;
                font-weight:800;
                color:#f4f6ff;
                margin-top:8px;
            ">
                {research_status}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# FEATURE STATUS
# ============================================================

st.markdown(
    '<div class="section-label">🧠 PRO V2 FEATURES</div>',
    unsafe_allow_html=True,
)

feature_col1, feature_col2, feature_col3 = st.columns(3)


with feature_col1:

    st.markdown(
        """
        <div class="glass-card">
            <div class="card-title">🔎 Intelligence</div>

            <div class="card-description">
                Multi-source research, source analysis,
                transcript intelligence and context detection.
            </div>

            <div class="status-small">
                ✓ Research<br>
                ✓ Relevance scoring<br>
                ✓ Hook detection<br>
                ✓ Reaction / payoff detection
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


with feature_col2:

    st.markdown(
        """
        <div class="glass-card">
            <div class="card-title">🧠 Story Engine</div>

            <div class="card-description">
                The selected footage is organized around
                retention-focused story roles.
            </div>

            <div class="status-small">
                ✓ Hook<br>
                ✓ Setup<br>
                ✓ Escalation<br>
                ✓ Reaction<br>
                ✓ Payoff<br>
                ✓ Ending
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


with feature_col3:

    st.markdown(
        """
        <div class="glass-card">
            <div class="card-title">🎬 Video Engine</div>

            <div class="card-description">
                Final rendering controls for vertical
                short-form output.
            </div>

            <div class="status-small">
                ✓ 9:16 output<br>
                ✓ Dynamic zoom<br>
                ✓ Captions<br>
                ✓ Audio normalization<br>
                ✓ Dead-space handling
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# FOOTER
# ============================================================

st.markdown(
    """
    <div class="footer">
        Auto Faceless Studio · Pro V2
        <br>
        Research → Story → Edit → Render
    </div>
    """,
    unsafe_allow_html=True,
)
