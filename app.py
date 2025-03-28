# app.py
import streamlit as st
from youtube_transcript_api import YouTubeTranscriptApi
from pdfminer.high_level import extract_text
import requests
import re
import json

OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]


def extract_video_id(youtube_url):
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", youtube_url)
    return match.group(1) if match else None


def get_video_metadata(video_id):
    transcript = YouTubeTranscriptApi.get_transcript(video_id)
    full_text = " ".join([t["text"] for t in transcript])
    duration_secs = transcript[-1]["start"] + transcript[-1].get("duration", 0)
    word_count = len(full_text.split())
    return full_text, word_count, duration_secs


def get_transcript_summary(transcript: str) -> str:
    prompt = f"""
You are an expert NLP assistant. Analyze the following transcript:

Transcript:
\"\"\"
{transcript[:10000]}
\"\"\"

Return a concise summary of the transcript.
"""
    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        data=json.dumps(
            {
                "model": "deepseek/deepseek-chat:free",
                "messages": [{"role": "user", "content": prompt}],
            }
        ),
    )
    return response.json()["choices"][0]["message"]["content"]


def analyze_transcript_semantics(transcript_summary: str):
    prompt = (
        f"""
You are an expert NLP assistant. Analyze the following transcript:

Transcript:
\"\"\"
{transcript_summary}
\"\"\"
"""
        + """
Return a JSON object with the following fields:
- "tags": list of key content tags
- "industries": list of relevant industries

Return ONLY a valid JSON object with the following fields and NO extra text. Do not say anything else. Do not include markdown. Do not explain.

An example response is below:

{
  "tags": ["neural networks", "machine learning", "AI", "image recognition", "beginner-friendly"],
  "industries": ["finance", "healthcare", "technology"],
}
"""
    )
    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        data=json.dumps(
            {
                "model": "deepseek/deepseek-chat:free",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
            }
        ),
    )

    try:
        response_json_str = re.search(
            r"\{.*\}", response.json()["choices"][0]["message"]["content"], re.DOTALL
        ).group(0)
        parsed_json = json.loads(response_json_str)
        return parsed_json
    except Exception as e:
        print("Failed to parse JSON:", e)
        print(response.json()["choices"][0]["message"]["content"])
        return None


def analyze_transcript_structure(transcript):
    prompt = (
        f"""
You are an expert NLP assistant. Analyze the following transcript:

Transcript:
\"\"\"
{transcript[:2000]}...
\"\"\"
"""
        + """
Return a JSON object with the following fields:
- "jargon_score": 1-10 rating of how technical it is
- "reading_level": (e.g., 8th grade, college)

Return ONLY a valid JSON object with the following fields and NO extra text. Do not say anything else. Do not include markdown. Do not explain.

An example response is below:

{
  "jargon_score": 4,
  "reading_level": "10th grade",
}
"""
    )
    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        data=json.dumps(
            {
                "model": "deepseek/deepseek-chat:free",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
            }
        ),
    )

    try:
        response_json_str = re.search(
            r"\{.*\}", response.json()["choices"][0]["message"]["content"], re.DOTALL
        ).group(0)
        parsed_json = json.loads(response_json_str)
        return parsed_json
    except Exception as e:
        print("Failed to parse JSON:", e)
        print(response.json()["choices"][0]["message"]["content"])
        return None


# Streamlit UI
st.title("🔮 AI Digest")

video_url = None
uploaded_file = None
text = None

media_type = st.selectbox("Select input type:", ["Video", "PDF", "Text"], index=0)

if media_type == "Video":
    video_url = st.text_input("Paste a YouTube link:")
elif media_type == "PDF":
    uploaded_file = st.file_uploader("Upload a text file", type=["pdf"])
elif media_type == "Text":
    text = st.text_area("Paste text:")


def populate_ui(is_video: bool, transcript: str = None):
    with st.spinner("Processing media..."):
        if is_video:
            video_id = extract_video_id(video_url)
            transcript, word_count, duration_secs = get_video_metadata(video_id)
        summary = get_transcript_summary(transcript)
        semantics = analyze_transcript_semantics(summary)
        structure = analyze_transcript_structure(transcript)
        if is_video:
            st.video(video_url)

        st.subheader("📝 Summary")
        st.write(summary)

        st.subheader("🏷️ Tags")
        st.write(", ".join(semantics["tags"]))

        st.subheader("💼 Industries")
        st.write(", ".join(semantics["industries"]))

        st.subheader("📊 Accessibility")
        if is_video:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(
                    "Words Per Minute", f"{word_count / (duration_secs / 60):.1f}"
                )
                with st.expander("About WPM"):
                    st.write(
                        "Words Per Minute measures speaking speed. Too fast can be hard to follow, too slow can lose engagement. 120-150 WPM is considered comfortable for most listeners."
                    )
        else:
            col2, col3 = st.columns(2)
        with col2:
            st.metric("Jargon Score", f"{structure['jargon_score']:.1f}")
            with st.expander("About Jargon Score"):
                st.write(
                    "Jargon Score indicates how specialized the language is. Lower scores (0-5) mean more accessible content. Higher scores (6-10) indicate more technical content."
                )
        with col3:
            st.metric("Reading Level", structure["reading_level"])
            with st.expander("About Reading Level"):
                st.write(
                    "Reading Level, assessed based on sentence complexity and vocabulary, shows the education level needed to understand the content, from elementary to post-graduate."
                )


if video_url:
    populate_ui(is_video=True, transcript=None)
elif uploaded_file:
    populate_ui(is_video=False, transcript=extract_text(uploaded_file))
elif text:
    populate_ui(is_video=False, transcript=text)
