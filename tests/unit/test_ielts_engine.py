"""Comprehensive unit and integration tests for IELTS Master Coach."""

import pytest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from app.agent import (
    analyze_speaking_pace,
    analyze_writing_metrics,
    calculate_ielts_overall_band,
    generate_task1_chart,
    get_ielts_prompt,
    list_ielts_prompts,
    root_agent,
)
from app.a2ui_utils import a2ui_callback


def test_calculate_ielts_overall_band_rounding():
    """Test official Cambridge/IDP rounding rules."""
    # Exact average
    res1 = calculate_ielts_overall_band(7.0, 7.0, 7.0, 7.0)
    assert res1["overall_band"] == 7.0
    assert "C1" in res1["cefr_level"]

    # .25 rounds up to .5
    res2 = calculate_ielts_overall_band(6.5, 6.5, 6.0, 6.0)  # avg = 6.25
    assert res2["overall_band"] == 6.5

    # .75 rounds up to 1.0
    res3 = calculate_ielts_overall_band(6.5, 7.0, 6.5, 7.0)  # avg = 6.75
    assert res3["overall_band"] == 7.0

    # .125 rounds down to .0
    res4 = calculate_ielts_overall_band(6.0, 6.0, 6.0, 6.5)  # avg = 6.125
    assert res4["overall_band"] == 6.0

    # .875 rounds up to 1.0
    res5 = calculate_ielts_overall_band(7.5, 8.0, 8.0, 8.0)  # avg = 7.875
    assert res5["overall_band"] == 8.0
    assert "C1" in res5["cefr_level"]

    # Weakest skill identification
    res6 = calculate_ielts_overall_band(8.5, 8.0, 6.0, 8.0)
    assert "writing" in res6["weakest_skills"]


def test_analyze_writing_metrics_underlength_and_paragraphs():
    """Test essay length penalties, structure, and lexical analysis."""
    short_essay = (
        "In modern society, renewable energy is becoming increasingly important. "
        "Governments should invest in solar power to protect the environment."
    )
    metrics = analyze_writing_metrics(short_essay, task_type="task_2")
    assert metrics["has_underlength_penalty"] is True
    assert metrics["words_deficit"] > 150
    assert metrics["target_min_words"] == 250
    assert any("Underlength Warning" in fb for fb in metrics["diagnostic_feedback"])


def test_analyze_writing_metrics_full_essay():
    """Test standard 4-paragraph Task 2 essay metrics with >250 words."""
    full_essay = (
        "In contemporary society, the global transition towards sustainable energy has become one of the most widely debated topics among policymakers and environmental scientists worldwide. While fossil fuels have powered unprecedented economic growth throughout the industrial era, their catastrophic ecological consequences necessitate an urgent transition towards green alternatives. In my opinion, despite initial economic burdens, the shift towards renewable energy is entirely indispensable for long-term planetary survival.\n\n"
        "On the one hand, proponents rightly emphasize that renewable energy sources such as solar, wind, and hydroelectric generation mitigate anthropogenic climate change effectively. These clean energy mechanisms produce virtually zero greenhouse gas emissions during operation, which significantly reduces urban atmospheric pollution and decelerates the rate of global warming. Furthermore, investing in sustainable infrastructure stimulates economic diversification, generating millions of specialized engineering and technical jobs across various sectors for future generations.\n\n"
        "On the other hand, critics argue that the initial capital expenditure and technological transition present formidable logistical obstacles. Developing countries frequently lack the modern electrical grid capacity required to integrate variable renewable power efficiently without destabilizing existing domestic industries. Consequently, robust international cooperation, financial subsidies, and technological transfer frameworks must be established by wealthier nations to assist developing economies in overcoming these financial hurdles smoothly.\n\n"
        "In conclusion, although establishing comprehensive renewable infrastructure demands substantial initial financial commitment, the long-term environmental protection and economic resilience it provides make this transition essential. Governments worldwide must therefore prioritize sustainable energy policies and commit adequate public capital to ensure a greener, healthier future for all human societies without further delay. Taking decisive collective action today will safeguard natural habitats and guarantee global prosperity for centuries to come."
    )
    metrics = analyze_writing_metrics(full_essay, task_type="task_2")
    assert metrics["has_underlength_penalty"] is False
    assert metrics["word_count"] >= 250
    assert metrics["paragraph_count"] == 4
    assert metrics["lexical_diversity_ttr"] > 0.45


def test_analyze_speaking_pace():
    """Test speech pace (WPM) calculation and filler word detection."""
    # Standard fluent speech
    transcript = (
        "Well, in my perspective, living in a multicultural city offers remarkable cultural exposure. "
        "Residents can experience diverse cuisines, traditions, and perspectives on a daily basis."
    )
    pace = analyze_speaking_pace(transcript, duration_seconds=12.0)
    assert pace["words_per_minute"] > 100
    assert pace["duration_seconds"] == 12.0

    # Hesitant speech with filler words
    hesitant_transcript = (
        "Um, well, like, I think studying abroad is, uh, very beneficial, you know, "
        "because you meet, like, different people, um, from various backgrounds."
    )
    hesitant_pace = analyze_speaking_pace(hesitant_transcript, duration_seconds=15.0)
    assert hesitant_pace["total_filler_words"] >= 3
    assert len(hesitant_pace["filler_breakdown"]) > 0


def test_generate_task1_chart_integration():
    """Test Task 1 chart generator and Cloud Storage upload."""
    result = generate_task1_chart(
        chart_type="bar",
        topic="Education",
        title="Higher Education Enrollment Rates by Country (2015-2023)",
    )
    assert result["public_image_url"].startswith("https://storage.googleapis.com/")
    assert len(result["data_table"]) > 0
    assert "Higher Education" in result["title"]


def test_firestore_prompt_bank_integration():
    """Test Firestore question bank retrieval."""
    prompts = list_ielts_prompts()
    assert len(prompts) >= 1

    first_prompt_id = prompts[0]["prompt_id"]
    detail = get_ielts_prompt(first_prompt_id)
    assert "error" not in detail
    assert "topic" in detail


def test_a2ui_callback_transformation():
    """Test A2UI callback rewrapping into a2a datapart."""
    cue_card_json = """
    [
      {
        "beginRendering": {
          "surfaceId": "default",
          "root": "card_root"
        }
      },
      {
        "surfaceUpdate": {
          "surfaceId": "default",
          "components": [
            {
              "id": "card_root",
              "component": {
                "Card": {
                  "child": "col_1"
                }
              }
            },
            {
              "id": "col_1",
              "component": {
                "Column": {
                  "children": {
                    "explicitList": ["title_text"]
                  }
                }
              }
            },
            {
              "id": "title_text",
              "component": {
                "Text": {
                  "text": {"literalString": "Speaking Part 2 Cue Card"},
                  "usageHint": "h1"
                }
              }
            }
          ]
        }
      }
    ]
    """
    raw_response = LlmResponse(
        content=types.Content(
            role="model", parts=[types.Part(text=cue_card_json)]
        )
    )
    processed = a2ui_callback(None, raw_response)
    assert processed is not None
    assert processed.custom_metadata == {"a2a:response": "true"}
    assert len(processed.content.parts) == 2


def test_root_agent_registration():
    """Verify all 8 tools and dual callbacks on root_agent."""
    assert root_agent.name == "root_agent"
    assert root_agent.after_model_callback is not None
    assert root_agent.after_agent_callback is not None
    assert len(root_agent.tools) == 8
