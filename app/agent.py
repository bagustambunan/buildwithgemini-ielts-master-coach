# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import io
import os
import re
import uuid
from collections import Counter
from zoneinfo import ZoneInfo

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.cloud import firestore
from google.cloud import storage
from google.genai import types

from app.a2ui_utils import a2ui_callback

MODEL = "gemini-3.8-flash"
FIRESTORE_PROJECT_ID = "qwiklabs-gcp-03-e3b544ecf171"
COLLECTION_NAME = "ielts_prompts"
GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME", "ielts-master-coach-media-e3b544")

db = firestore.Client(project=FIRESTORE_PROJECT_ID)
storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)


async def generate_memories_callback(callback_context: CallbackContext):
    """Saves session events to Vertex AI Memory Bank across turns."""
    await callback_context.add_session_to_memory()
    return None


def list_ielts_prompts(skill: str = "", topic: str = "") -> list[dict]:
    """Retrieves practice prompts from the IELTS question bank in Firestore.

    Args:
        skill: Optional filter for IELTS skill ('speaking', 'writing', 'reading', 'listening').
        topic: Optional filter for topic category (e.g. 'Environment', 'Travel', 'Education', 'Technology').

    Returns:
        A list of prompt records containing prompt_id, title, skill, section, topic, and prompt text.
    """
    collection = db.collection(COLLECTION_NAME)
    query = collection

    if skill:
        query = query.where(field_path="skill", op_string="==", value=skill.lower().strip())
    if topic:
        query = query.where(field_path="topic", op_string="==", value=topic.strip())

    docs = query.stream()
    results = []
    for doc in docs:
        data = doc.to_dict()
        results.append({
            "prompt_id": data.get("prompt_id", doc.id),
            "title": data.get("title", ""),
            "skill": data.get("skill", ""),
            "section": data.get("section", ""),
            "topic": data.get("topic", ""),
            "target_band": data.get("target_band", 7.0),
            "prompt_text": data.get("prompt_text", ""),
            "cue_points": data.get("cue_points", []),
            "key_vocabulary": data.get("key_vocabulary", []),
        })
    return results


def get_ielts_prompt(prompt_id: str) -> dict:
    """Gets complete details of a specific IELTS prompt by its unique ID.

    Args:
        prompt_id: The ID of the prompt (e.g. 'writing-t2-env-01', 'speaking-p2-travel-01').

    Returns:
        A dictionary with full prompt details, including model answer and collocations.
    """
    doc_ref = db.collection(COLLECTION_NAME).document(prompt_id.strip())
    doc = doc_ref.get()
    if not doc.exists:
        return {"error": f"Prompt with ID '{prompt_id}' was not found in Firestore."}
    return doc.to_dict()


def save_ielts_prompt(
    prompt_id: str,
    skill: str,
    section: str,
    topic: str,
    title: str,
    prompt_text: str,
    target_band: float = 7.5,
    key_vocabulary: list[str] = None,
    cue_points: list[str] = None,
    model_answer: str = "",
) -> str:
    """Saves or creates a new practice prompt in the IELTS question bank in Firestore.

    Args:
        prompt_id: Unique slug for the prompt (e.g. 'writing-t2-tech-02').
        skill: The IELTS skill ('speaking', 'writing', 'reading', 'listening').
        section: Section name (e.g. 'task_1', 'task_2', 'part_1', 'part_2', 'part_3').
        topic: Topic domain (e.g. 'Technology', 'Healthcare', 'Society').
        title: Short descriptive title.
        prompt_text: The full question prompt or cue card instructions.
        target_band: Target band standard (e.g. 7.5).
        key_vocabulary: Optional list of high-band academic collocations/idioms.
        cue_points: Optional bullet points for speaking cue cards.
        model_answer: Optional sample Band 8/9 model response.

    Returns:
        Confirmation message with the created prompt ID.
    """
    doc_ref = db.collection(COLLECTION_NAME).document(prompt_id.strip())
    payload = {
        "prompt_id": prompt_id.strip(),
        "skill": skill.lower().strip(),
        "section": section.lower().strip(),
        "topic": topic.strip(),
        "title": title.strip(),
        "prompt_text": prompt_text.strip(),
        "target_band": target_band,
        "key_vocabulary": key_vocabulary or [],
        "cue_points": cue_points or [],
        "model_answer": model_answer.strip(),
    }
    doc_ref.set(payload)
    return f"Successfully saved IELTS prompt '{prompt_id}' ({title}) to Firestore."


def calculate_ielts_overall_band(
    listening: float,
    reading: float,
    writing: float,
    speaking: float,
) -> dict:
    """Calculates the official IELTS Overall Band Score from 4 skill sub-scores using Cambridge/IDP rounding rules.

    Args:
        listening: Listening band score (0.0 to 9.0 in increments of 0.5).
        reading: Reading band score (0.0 to 9.0 in increments of 0.5).
        writing: Writing band score (0.0 to 9.0 in increments of 0.5).
        speaking: Speaking band score (0.0 to 9.0 in increments of 0.5).

    Returns:
        A dictionary with raw_average, overall_band, cefr_level, scores breakdown, and improvement advice.
    """
    scores = {
        "listening": float(listening),
        "reading": float(reading),
        "writing": float(writing),
        "speaking": float(speaking),
    }

    raw_average = sum(scores.values()) / 4.0
    base = int(raw_average)
    fraction = raw_average - base

    if fraction < 0.25:
        overall_band = float(base)
    elif fraction < 0.75:
        overall_band = float(base) + 0.5
    else:
        overall_band = float(base) + 1.0

    overall_band = max(0.0, min(9.0, overall_band))

    if overall_band >= 8.5:
        cefr_level = "C2 (Proficient User / Mastery)"
    elif overall_band >= 7.0:
        cefr_level = "C1 (Effective Operational Proficiency)"
    elif overall_band >= 5.5:
        cefr_level = "B2 (Vantage / Upper Intermediate)"
    elif overall_band >= 4.0:
        cefr_level = "B1 (Threshold / Intermediate)"
    else:
        cefr_level = "A2/A1 (Basic User)"

    min_score = min(scores.values())
    weakest_skills = [skill for skill, val in scores.items() if val == min_score]
    advice = (
        f"Your lowest scoring component is {', '.join(weakest_skills)} at {min_score}. "
        f"Lifting your lowest score by 0.5 is the most effective lever to raise your overall band."
    )

    return {
        "raw_average": round(raw_average, 3),
        "overall_band": overall_band,
        "cefr_level": cefr_level,
        "scores": scores,
        "weakest_skills": weakest_skills,
        "advice": advice,
    }


def analyze_writing_metrics(
    essay_text: str,
    task_type: str = "task_2",
) -> dict:
    """Analyzes an IELTS writing submission for word count penalties, lexical diversity, and sentence structure complexity.

    Args:
        essay_text: The complete text of the student's essay or report.
        task_type: 'task_1' (min 150 words) or 'task_2' (min 250 words).

    Returns:
        A dictionary with word count, penalty status, lexical diversity (TTR), sentence statistics, and overused words.
    """
    cleaned_text = essay_text.strip()
    words = re.findall(r"\b\w+\b", cleaned_text)
    word_count = len(words)

    paragraphs = [p for p in re.split(r"\n\s*\n", cleaned_text) if p.strip()]
    paragraph_count = max(1, len(paragraphs))

    target_min_words = 150 if task_type.lower() == "task_1" else 250
    has_underlength_penalty = word_count < target_min_words
    words_deficit = max(0, target_min_words - word_count)

    lowered_words = [w.lower() for w in words]
    unique_words = set(lowered_words)
    ttr = round(len(unique_words) / word_count, 3) if word_count > 0 else 0.0

    if ttr >= 0.55:
        lexical_rating = "High Lexical Range (Strong Band 7.5+ indicator)"
    elif ttr >= 0.42:
        lexical_rating = "Moderate Lexical Range (Typical Band 6.0-6.5)"
    else:
        lexical_rating = "Repetitive Vocabulary (High risk of Band 5.5 or below in LR)"

    sentences = [s.strip() for s in re.split(r"[.!?]+", cleaned_text) if s.strip()]
    sentence_count = max(1, len(sentences))
    sentence_lengths = [len(re.findall(r"\b\w+\b", s)) for s in sentences]
    avg_sentence_len = round(sum(sentence_lengths) / sentence_count, 1)

    run_on_sentences = [
        s for s, count in zip(sentences, sentence_lengths) if count >= 35
    ]

    stopwords = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with",
        "by", "from", "up", "about", "into", "over", "after", "is", "are", "was", "were",
        "be", "been", "being", "have", "has", "had", "do", "does", "did", "can", "could",
        "should", "would", "will", "this", "that", "these", "those", "it", "its", "they",
        "them", "their", "we", "us", "our", "you", "your", "he", "him", "his", "she", "her",
        "i", "my", "me", "as", "if", "than", "so", "because", "while", "which", "who", "whom"
    }
    content_words = [w for w in lowered_words if w not in stopwords and len(w) > 2]
    word_freq = Counter(content_words)
    overused_words = [
        {"word": word, "occurrences": count}
        for word, count in word_freq.most_common(5)
        if count >= 4
    ]

    feedback_points = []
    if has_underlength_penalty:
        feedback_points.append(
            f"Underlength Warning: Essay contains {word_count} words ({words_deficit} words below the {target_min_words}-word minimum). This carries an automatic Task Response penalty."
        )
    else:
        feedback_points.append(
            f"Word Count OK: {word_count} words (meets the {target_min_words}-word target)."
        )

    if paragraph_count < 4 and task_type.lower() == "task_2":
        feedback_points.append(
            f"Paragraph Structure: Detected only {paragraph_count} paragraphs. Standard Task 2 requires 4-5 clear paragraphs (Introduction, 2-3 Body Paragraphs, Conclusion)."
        )

    if run_on_sentences:
        feedback_points.append(
            f"Run-on Sentences: Detected {len(run_on_sentences)} overly long sentence(s) (>= 35 words). Splitting these into compound-complex sentences will prevent grammar slips."
        )

    return {
        "word_count": word_count,
        "target_min_words": target_min_words,
        "has_underlength_penalty": has_underlength_penalty,
        "words_deficit": words_deficit,
        "paragraph_count": paragraph_count,
        "lexical_diversity_ttr": ttr,
        "lexical_rating": lexical_rating,
        "average_sentence_length": avg_sentence_len,
        "run_on_sentences_count": len(run_on_sentences),
        "run_on_samples": run_on_sentences[:2],
        "overused_words": overused_words,
        "diagnostic_feedback": feedback_points,
    }


def generate_task1_chart(
    chart_type: str = "line",
    topic: str = "Energy",
    title: str = "Renewable Energy Production Trends (2010-2022)",
) -> dict:
    """Generates an authentic Academic Writing Task 1 statistical visualization, uploads it to the public GCS bucket, and returns the public URL.

    Args:
        chart_type: Type of chart: 'line', 'bar', or 'pie'.
        topic: Topic domain (e.g. 'Energy', 'Education', 'Transportation', 'Tourism').
        title: Title of the chart.

    Returns:
        A dictionary with public_image_url, chart_type, title, key_data_points, and overview_prompt.
    """
    fig, ax = plt.subplots(figsize=(7.5, 4.5), dpi=130)

    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#F8F9FA")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#BDC1C6")
    ax.spines["bottom"].set_color("#BDC1C6")
    ax.grid(True, linestyle="--", alpha=0.5, color="#DADCE0")

    dataset_summary = []

    if chart_type.lower() == "bar":
        categories = ["UK", "USA", "Australia", "Canada", "Germany"]
        values_2015 = [45, 80, 35, 50, 30]
        values_2025 = [65, 95, 55, 85, 48]
        x = range(len(categories))
        width = 0.35

        ax.bar([i - width/2 for i in x], values_2015, width, label="2015", color="#1a73e8")
        ax.bar([i + width/2 for i in x], values_2025, width, label="2025 (Projected)", color="#34a853")
        ax.set_xticks(list(x))
        ax.set_xticklabels(categories, fontsize=10)
        ax.set_ylabel("Thousand Metric Tons / Index Units", fontsize=10)
        dataset_summary = [
            {"category": cat, "2015": v15, "2025": v25}
            for cat, v15, v25 in zip(categories, values_2015, values_2025)
        ]
    elif chart_type.lower() == "pie":
        labels = ["Solar", "Wind", "Hydroelectric", "Natural Gas", "Coal"]
        sizes = [30, 25, 20, 15, 10]
        colors = ["#1a73e8", "#34a853", "#fbbc04", "#ea4335", "#5f6368"]
        ax.pie(sizes, labels=labels, autopct="%1.1f%%", startangle=140, colors=colors)
        dataset_summary = [{"source": l, "share_percentage": s} for l, s in zip(labels, sizes)]
    else:  # Default: line graph
        years = [2010, 2013, 2016, 2019, 2022]
        solar = [12, 22, 38, 59, 88]
        wind = [25, 33, 44, 58, 72]
        coal = [80, 75, 68, 55, 42]

        ax.plot(years, solar, marker="o", color="#1a73e8", linewidth=2.5, label="Solar Energy")
        ax.plot(years, wind, marker="s", color="#34a853", linewidth=2.5, label="Wind Energy")
        ax.plot(years, coal, marker="^", color="#ea4335", linewidth=2.5, linestyle="--", label="Coal Power")
        ax.set_xlabel("Year", fontsize=10)
        ax.set_ylabel("Production (Terawatt-Hours)", fontsize=10)
        ax.set_xticks(years)
        dataset_summary = [
            {"year": yr, "solar": s, "wind": w, "coal": c}
            for yr, s, w, c in zip(years, solar, wind, coal)
        ]

    ax.set_title(title, fontsize=12, pad=14, fontweight="bold", color="#202124")
    if chart_type.lower() != "pie":
        ax.legend(loc="upper left", frameon=True, facecolor="#FFFFFF", edgecolor="#DADCE0")

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)

    file_id = f"task1_{uuid.uuid4().hex[:8]}.png"
    blob_path = f"task1_charts/{file_id}"
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(blob_path)
    blob.upload_from_file(buf, content_type="image/png")

    public_image_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{blob_path}"

    return {
        "public_image_url": public_image_url,
        "chart_type": chart_type,
        "topic": topic,
        "title": title,
        "data_table": dataset_summary,
        "overview_prompt": (
            "Summarize the information by selecting and reporting the main features, "
            "and make comparisons where relevant. Write at least 150 words."
        ),
    }


def analyze_speaking_pace(
    transcript: str,
    duration_seconds: float,
) -> dict:
    """Analyzes a spoken response for speech rate (WPM), hesitations, and conversational fluency tempo.

    Args:
        transcript: The text transcript of the spoken answer.
        duration_seconds: The spoken response duration in seconds.

    Returns:
        A dictionary with words_per_minute, word_count, fluency_rating, filler_words_detected, and pacing_advice.
    """
    words = re.findall(r"\b\w+\b", transcript.strip())
    word_count = len(words)
    duration_sec = max(1.0, float(duration_seconds))
    wpm = round((word_count / duration_sec) * 60.0, 1)

    if wpm >= 165:
        fluency_rating = "Slightly Rushed (Risk of compromised articulation)"
        pacing_advice = "Slow down slightly to emphasize key content words and give yourself time to formulate complex sentence structures."
    elif wpm >= 115:
        fluency_rating = "Optimal Natural Pace (Band 7.5 - 8.5 Fluency benchmark)"
        pacing_advice = "Excellent pacing. Maintain this natural rhythm with varied intonation and coherent discourse markers."
    elif wpm >= 90:
        fluency_rating = "Moderate / Slightly Hesitant (Typical Band 6.0 - 6.5)"
        pacing_advice = "Good clarity, but aim to reduce pauses between clauses to achieve a smoother, more connected flow."
    else:
        fluency_rating = "Slow / Frequent Pauses (Band 5.0 - 5.5 Fluency range)"
        pacing_advice = "Work on chunking words together into thought groups to reduce hesitation while searching for vocabulary."

    filler_patterns = [r"\bum\b", r"\buh\b", r"\ber\b", r"\bah\b", r"\blike\b", r"\byou know\b", r"\bbasically\b", r"\bactually\b", r"\bsort of\b", r"\bkind of\b"]
    filler_counts = {}
    total_fillers = 0
    lower_transcript = transcript.lower()

    for pat in filler_patterns:
        clean_name = pat.replace(r"\b", "")
        matches = len(re.findall(pat, lower_transcript))
        if matches > 0:
            filler_counts[clean_name] = matches
            total_fillers += matches

    return {
        "words_per_minute": wpm,
        "word_count": word_count,
        "duration_seconds": round(duration_sec, 1),
        "fluency_rating": fluency_rating,
        "total_filler_words": total_fillers,
        "filler_breakdown": filler_counts,
        "pacing_advice": pacing_advice,
    }


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "You are IELTS Master Coach, an expert, encouraging, and rigorous AI tutor specializing in helping candidates "
        "master all 4 skills of the IELTS exam (Speaking, Writing, Reading, and Listening) to break past the Band 6.5 plateau "
        "and achieve Band 7.5 - 8.5+.\n\n"
        "### Core Capabilities & Memory:\n"
        "- You remember candidate target band scores, persistent grammar/pronunciation errors, and practice history across sessions.\n"
        "- You have access to a rich suite of specialized IELTS tools:\n"
        "  * `PreloadMemoryTool`: automatically recalls user preferences and learning history across sessions.\n"
        "  * `list_ielts_prompts`: browse practice questions by skill or topic in Firestore.\n"
        "  * `get_ielts_prompt`: inspect complete prompt details, cue cards, and model answers.\n"
        "  * `save_ielts_prompt`: store custom prompts in Firestore.\n"
        "  * `calculate_ielts_overall_band`: compute the official overall band score and CEFR level from 4 sub-scores.\n"
        "  * `analyze_writing_metrics`: evaluate essay word counts, length penalties, lexical diversity (TTR), and run-on sentences.\n"
        "  * `generate_task1_chart`: generate authentic Academic Task 1 graphs and upload to Cloud Storage.\n"
        "  * `analyze_speaking_pace`: calculate Words Per Minute (WPM) and detect speech filler words.\n\n"
        "### A2UI Presentation Guidelines (A2UI v0.8):\n"
        "When the user requests practice materials (e.g. Speaking Part 2 Cue Cards, Task 1 Visual Prompts, Diagnostic Scorecards, or Vocabulary Flashcards), "
        "emit a structured A2UI v0.8 JSON array to display interactive cards.\n"
        "Rules for A2UI output:\n"
        "1. Keep every surface small, elegant, and flat: ONE Card > ONE Column > a list of Text, Row, or Image components.\n"
        "2. Never nest a Card inside a Card.\n"
        "3. Use only these components: Card, Column, Row, Text, Image, Divider.\n"
        "4. Use usageHint property ('h1', 'h2', 'body') on Text components for styling. Do not use raw markdown in literalString.\n"
        "5. When including an Image, only use a valid public https:// URL (such as from `generate_task1_chart` or `https://storage.googleapis.com/...`).\n"
        "6. When returning A2UI JSON, output ONLY the raw JSON array starting with `beginRendering` and `surfaceUpdate`.\n\n"
        "Always guide users systematically with feedback grounded in official Cambridge IELTS band descriptors."
    ),
    tools=[
        PreloadMemoryTool(),
        list_ielts_prompts,
        get_ielts_prompt,
        save_ielts_prompt,
        calculate_ielts_overall_band,
        analyze_writing_metrics,
        generate_task1_chart,
        analyze_speaking_pace,
    ],
    after_model_callback=a2ui_callback,
    after_agent_callback=generate_memories_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
