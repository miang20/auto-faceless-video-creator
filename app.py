import json
import urllib.request

import streamlit as st

from core.config import (
    DEFAULT_MAX_CLIPS,
    DEFAULT_LANGUAGE,
    DEFAULT_MAKE_VERTICAL,
    DEFAULT_KEEP_AUDIO,
    DEFAULT_RESEARCH_LIMIT,
    GITHUB_OWNER,
    GITHUB_REPO,
)

from core.github_jobs import create_github_job

from core.orchestrator import (
    create_orchestrator_job,
    execute_topic_job,
)

from core.validator import (
    validate_video_url,
    validate_reference_url,
)


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Auto Faceless Video Creator",
    page_icon="🎬",
    layout="wide",
)


# ============================================================
# HELPERS
# ============================================================

def get_github_token() -> str:
    """
    Get GitHub token from Streamlit secrets.
    """

    token = st.secrets.get("GITHUB_TOKEN")

    if not token:
        raise RuntimeError(
            "GITHUB_TOKEN is missing from Streamlit secrets."
        )

    return token


def get_github_jobs(token: str):
    """
    Read recent job JSON files from GitHub.
    """

    url = (
        f"https://api.github.com/repos/"
        f"{GITHUB_OWNER}/{GITHUB_REPO}/contents/jobs"
    )

    request = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )

    try:

        with urllib.request.urlopen(
            request,
            timeout=30,
        ) as response:

            data = json.loads(
                response.read().decode("utf-8")
            )

        jobs = []

        for item in data:

            if not item.get(
                "name",
                "",
            ).endswith(".json"):
                continue

            try:

                file_url = item.get(
                    "download_url"
                )

                if not file_url:
                    continue

                file_request = urllib.request.Request(
                    file_url,
                    method="GET",
                )

                with urllib.request.urlopen(
                    file_request,
                    timeout=15,
                ) as file_response:

                    job_data = json.loads(
                        file_response.read().decode("utf-8")
                    )

                jobs.append(job_data)

            except Exception:
                continue

        jobs.sort(
            key=lambda x: x.get(
                "created_at",
                "",
            ),
            reverse=True,
        )

        return jobs

    except Exception:
        return []


def display_job_status(status: str):
    """
    Render a consistent job status indicator.
    """

    status_upper = (
        status or "unknown"
    ).upper()

    if status_upper == "COMPLETED":

        st.success(status_upper)

    elif status_upper == "FAILED":

        st.error(status_upper)

    elif status_upper in {
        "DOWNLOADING",
        "PROCESSING",
    }:

        st.warning(status_upper)

    else:

        st.info(status_upper)


# ============================================================
# HEADER
# ============================================================

st.title(
    "🎬 Auto Faceless Video Creator"
)
st.caption("Pro V2 • Clean Streamlit UI")

st.caption(
    "V2 Control Center • "
    "Research • Analysis • GitHub Queue • Termux Worker"
)

st.divider()


# ============================================================
# SYSTEM STATUS
# ============================================================

st.subheader("🟢 System Status")

status1, status2, status3, status4 = st.columns(4)

with status1:
    st.success("GitHub\nConnected")

with status2:
    st.success("Job Queue\nReady")

with status3:
    st.success("Research Engine\nReady")

with status4:
    st.success("Pipeline\nReady")


st.divider()


# ============================================================
# CREATE JOB
# ============================================================

st.subheader("🚀 Create New Video Job")

input_mode = st.selectbox(
    "What do you want to create?",
    [
        "YouTube Video URL",
        "Topic",
        "Idea",
        "Keyword",
    ],
)


# ============================================================
# INPUT
# ============================================================

if input_mode == "YouTube Video URL":

    input_value = st.text_input(
        "YouTube Video URL",
        placeholder=(
            "https://www.youtube.com/watch?v=..."
        ),
    )

else:

    input_value = st.text_input(
        input_mode,
        placeholder=(
            f"Enter your "
            f"{input_mode.lower()}..."
        ),
    )


reference_url = st.text_input(
    "Reference URL (Optional)",
    placeholder=(
        "Paste a YouTube video/channel/"
        "reference URL..."
    ),
)


# ============================================================
# ADVANCED SETTINGS
# ============================================================

with st.expander("⚙️ Pipeline Settings"):

    col1, col2, col3 = st.columns(3)

    with col1:

        research_limit = st.number_input(
            "Research Sources",
            min_value=1,
            max_value=50,
            value=DEFAULT_RESEARCH_LIMIT,
            step=1,
        )

    with col2:

        max_clips = st.number_input(
            "Maximum Clips",
            min_value=1,
            max_value=100,
            value=DEFAULT_MAX_CLIPS,
            step=1,
        )

    with col3:

        language = st.selectbox(
            "Language",
            ["en"],
            index=0,
        )

    make_vertical = st.checkbox(
        "Create vertical clips (9:16)",
        value=DEFAULT_MAKE_VERTICAL,
    )

    keep_audio = st.checkbox(
        "Keep extracted audio files",
        value=DEFAULT_KEEP_AUDIO,
    )


# ============================================================
# BUTTON
# ============================================================

if input_mode == "YouTube Video URL":

    button_label = (
        "🚀 CREATE VIDEO JOB"
    )

else:

    button_label = (
        "🔎 RESEARCH & ANALYZE"
    )


if st.button(
    button_label,
    type="primary",
    use_container_width=True,
):

    # --------------------------------------------------------
    # BASIC INPUT CHECK
    # --------------------------------------------------------

    if not input_value.strip():

        st.warning(
            f"Please enter a "
            f"{input_mode.lower()}."
        )

        st.stop()


    # ========================================================
    # YOUTUBE VIDEO URL WORKFLOW
    # ========================================================

    if input_mode == "YouTube Video URL":

        try:

            video_url = validate_video_url(
                input_value
            )

            reference = validate_reference_url(
                reference_url
            )

            github_token = get_github_token()

            with st.spinner(
                "Creating GitHub video job..."
            ):

                job = create_orchestrator_job(
                    job_type="video",
                    input_value=video_url,
                    reference_url=reference,
                )

                job_path = create_github_job(
                    token=github_token,
                    job=job,
                )

            st.success(
                "✅ Video job successfully added "
                "to the GitHub queue."
            )

            st.write("Job ID")

            st.code(
                job["job_id"]
            )

            st.write("Queue Path")

            st.code(
                job_path
            )

            st.info(
                "Termux worker will pick up the "
                "queued job and run the processing pipeline."
            )

        except Exception as exc:

            st.error(
                "❌ Failed to create video job."
            )

            st.exception(exc)


    # ========================================================
    # TOPIC / IDEA / KEYWORD WORKFLOW
    # ========================================================

    else:

        try:

            with st.spinner(
                "🔎 Researching topic, analyzing sources "
                "and generating the production plan..."
            ):

                result = execute_topic_job(
                    topic=input_value.strip(),
                    reference_url=(
                        reference_url.strip()
                        if reference_url.strip()
                        else None
                    ),
                    research_limit=int(
                        research_limit
                    ),
                )

            if not result.get("success"):

                st.error(
                    "❌ Topic pipeline failed."
                )

                if result.get("error"):

                    st.error(
                        result["error"]
                    )

                st.stop()


            # ------------------------------------------------
            # RESULT DATA
            # ------------------------------------------------

            research = result.get(
                "research",
                {},
            )

            source_analysis = result.get(
                "source_analysis",
                {},
            )

            script = result.get(
                "script",
                {},
            )

            sources = research.get(
                "sources",
                [],
            )

            analyzed_sources = source_analysis.get(
                "sources",
                [],
            )


            # ------------------------------------------------
            # SUMMARY
            # ------------------------------------------------

            st.success(
                "✅ Research + source analysis + "
                "script planning completed."
            )

            metric1, metric2, metric3 = st.columns(3)

            with metric1:

                st.metric(
                    "Sources Found",
                    len(sources),
                )

            with metric2:

                st.metric(
                    "Sources Analyzed",
                    len(analyzed_sources),
                )

            with metric3:

                st.metric(
                    "Script Sections",
                    len(
                        script.get(
                            "sections",
                            [],
                        )
                    ),
                )


            # =================================================
            # RESEARCH SOURCES
            # =================================================

            if sources:

                st.subheader(
                    "🎥 Research Sources"
                )

                for index, source in enumerate(
                    sources,
                    start=1,
                ):

                    title = source.get(
                        "title",
                        "Untitled",
                    )

                    video_url = source.get(
                        "url",
                        "",
                    )

                    video_id = source.get(
                        "video_id",
                        "",
                    )

                    with st.container(
                        border=True
                    ):

                        st.write(
                            f"**{index}. {title}**"
                        )

                        if video_id:

                            st.caption(
                                f"Video ID: {video_id}"
                            )

                        if video_url:

                            st.link_button(
                                "▶️ Open YouTube Video",
                                video_url,
                            )


            else:

                st.warning(
                    "No YouTube sources were found."
                )


            # =================================================
            # SOURCE ANALYSIS
            # =================================================

            if analyzed_sources:

                st.subheader(
                    "📊 Source Analysis"
                )

                for index, source in enumerate(
                    analyzed_sources[:10],
                    start=1,
                ):

                    title = source.get(
                        "title",
                        "Untitled",
                    )

                    score = source.get(
                        "final_score",
                        source.get(
                            "score",
                            0,
                        ),
                    )

                    with st.container(
                        border=True
                    ):

                        st.write(
                            f"**#{index} {title}**"
                        )

                        st.caption(
                            f"Source Score: {score}"
                        )


            # =================================================
            # SCRIPT / EDITING PLAN
            # =================================================

            if script:

                st.subheader(
                    "📝 Production Plan"
                )

                hook = script.get(
                    "hook"
                )

                if hook:

                    st.write(
                        "**Hook:**"
                    )

                    st.info(
                        hook
                    )

                sections = script.get(
                    "sections",
                    [],
                )

                if sections:

                    st.write(
                        "**Script / Story Structure:**"
                    )

                    for index, section in enumerate(
                        sections,
                        start=1,
                    ):

                        if isinstance(
                            section,
                            dict,
                        ):

                            title = section.get(
                                "title",
                                f"Section {index}",
                            )

                            text = section.get(
                                "text",
                                section.get(
                                    "content",
                                    "",
                                ),
                            )

                            st.markdown(
                                f"**{index}. {title}**"
                            )

                            if text:

                                st.write(
                                    text
                                )

                        else:

                            st.write(
                                f"{index}. {section}"
                            )


            # =================================================
            # ARTIFACTS
            # =================================================

            artifacts = result.get(
                "artifacts",
                {},
            )

            if artifacts:

                with st.expander(
                    "📁 Pipeline Artifacts"
                ):

                    for name, path in artifacts.items():

                        if path:

                            st.write(
                                f"**{name}:**"
                            )

                            st.code(
                                str(path)
                            )


        except Exception as exc:

            st.error(
                "❌ Research / analysis failed."
            )

            st.exception(exc)


st.divider()


# ============================================================
# RECENT JOBS
# ============================================================

st.subheader(
    "📋 Recent Jobs"
)

if st.button(
    "🔄 Refresh Jobs",
    use_container_width=True,
):

    try:

        github_token = get_github_token()

        jobs = get_github_jobs(
            github_token
        )

        if not jobs:

            st.info(
                "No jobs found."
            )

        else:

            for job in jobs[:10]:

                job_id = job.get(
                    "job_id",
                    "Unknown",
                )

                status = job.get(
                    "status",
                    "unknown",
                )

                job_type = job.get(
                    "job_type",
                    "unknown",
                )

                input_value = job.get(
                    "input_value",
                    "",
                )

                reference = job.get(
                    "reference_url",
                    "",
                )

                created_at = job.get(
                    "created_at",
                    "",
                )

                result_path = job.get(
                    "result_path",
                    "",
                )

                error = job.get(
                    "error",
                    "",
                )

                with st.container(
                    border=True
                ):

                    col1, col2, col3 = st.columns(
                        [3, 1, 2]
                    )

                    with col1:

                        st.write(
                            f"**{job_id}**"
                        )

                        st.caption(
                            input_value
                        )

                        if reference:

                            st.caption(
                                f"Reference: {reference}"
                            )

                        if error:

                            st.error(
                                error
                            )

                    with col2:

                        display_job_status(
                            status
                        )

                    with col3:

                        st.caption(
                            f"Type: {job_type}"
                        )

                        st.caption(
                            created_at
                        )

                        if result_path:

                            st.caption(
                                f"Result: {result_path}"
                            )

    except Exception as exc:

        st.error(
            "❌ Could not load jobs."
        )

        st.exception(exc)

else:

    st.info(
        "Press **Refresh Jobs** to view "
        "the latest queue."
    )


st.divider()


# ============================================================
# FOOTER
# ============================================================

st.caption(
    "Auto Faceless Video Creator V2 • "
    "Input → Validation → Research → Analysis → "
    "Pipeline → GitHub Queue → Termux"
)
