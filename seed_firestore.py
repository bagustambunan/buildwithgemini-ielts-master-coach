#!/usr/bin/env python3
"""Seed script for IELTS Master Coach Firestore collection."""

from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-03-e3b544ecf171"
COLLECTION_NAME = "ielts_prompts"

SEEDED_PROMPTS = [
    {
        "prompt_id": "writing-t2-env-01",
        "skill": "writing",
        "section": "task_2",
        "topic": "Environment",
        "title": "Fossil Fuels vs Renewable Energy Investment",
        "prompt_text": "Some people believe that the best way to solve environmental problems is to increase the price of fuel. Others argue that alternative measures are needed. Discuss both views and give your own opinion.",
        "cue_points": [],
        "target_band": 7.5,
        "key_vocabulary": [
            "fiscal disincentive",
            "renewable energy infrastructure",
            "carbon footprint",
            "sustainable alternative",
            "environmentally viable"
        ],
        "model_answer": "While raising fuel levies can serve as a potent fiscal deterrent against excessive consumption, systemic transition toward green public transit and subsidized solar energy yields more lasting environmental remedies."
    },
    {
        "prompt_id": "speaking-p2-travel-01",
        "skill": "speaking",
        "section": "part_2",
        "topic": "Travel",
        "title": "A Memorable Journey Using Public Transport",
        "prompt_text": "Describe a memorable journey you made by public transport.",
        "cue_points": [
            "Where you went and what form of transport you used",
            "Who you traveled with",
            "What happened during the journey",
            "Why this journey was particularly memorable to you"
        ],
        "target_band": 7.5,
        "key_vocabulary": [
            "breathtaking scenery",
            "scenic coastal route",
            "spontaneous detour",
            "unforgettable camaraderie",
            "seamless commute"
        ],
        "model_answer": "I would like to talk about a cross-country train excursion across Hokkaido in Japan, where the winter scenery and spontaneous conversations with fellow commuters left an indelible impression on me."
    },
    {
        "prompt_id": "writing-t1-chart-01",
        "skill": "writing",
        "section": "task_1",
        "topic": "Education",
        "title": "International Student Enrollment Trends",
        "prompt_text": "The line graph illustrates the number of international students enrolled in universities across four countries (UK, USA, Australia, Canada) between 2010 and 2020.",
        "cue_points": [],
        "target_band": 7.5,
        "key_vocabulary": [
            "experienced an upward trajectory",
            "plateaued around",
            "surpassed the counterpart",
            "notable divergence",
            "peak figure"
        ],
        "model_answer": "Overall, while the USA consistently maintained the highest student cohort throughout the decade, Canada demonstrated the most pronounced exponential growth."
    },
    {
        "prompt_id": "speaking-p3-tech-01",
        "skill": "speaking",
        "section": "part_3",
        "topic": "Technology",
        "title": "Impact of Artificial Intelligence on Future Employment",
        "prompt_text": "How will artificial intelligence reshape the job market for the next generation of university graduates?",
        "cue_points": [],
        "target_band": 8.0,
        "key_vocabulary": [
            "cognitive automation",
            "synergistic collaboration",
            "obsolete vocational skills",
            "adaptability and critical thinking"
        ],
        "model_answer": "Rather than causing widespread redundancy, AI is poised to automate routine cognitive tasks, shifting employer demand toward creative problem-solving and ethical governance."
    },
    {
        "prompt_id": "reading-academic-01",
        "skill": "reading",
        "section": "academic_passage",
        "topic": "Science",
        "title": "Bioluminescence in Marine Ecosystems",
        "prompt_text": "Read the excerpt on luciferin-luciferase enzymatic reactions in deep-sea cephalopods and identify whether statements are True, False, or Not Given.",
        "cue_points": [],
        "target_band": 7.0,
        "key_vocabulary": [
            "photophores",
            "counter-illumination",
            "abyssal zone",
            "evolutionary adaptation"
        ],
        "model_answer": "Statement 1 is True because photophores produce light precisely matching downwelling solar radiation."
    }
]

def seed():
    print(f"Connecting to Firestore for project '{PROJECT_ID}'...")
    db = firestore.Client(project=PROJECT_ID)
    collection = db.collection(COLLECTION_NAME)
    
    for item in SEEDED_PROMPTS:
        doc_ref = collection.document(item["prompt_id"])
        doc_ref.set(item)
        print(f"  [Seeded] {item['prompt_id']} - {item['title']} ({item['skill'].upper()})")
        
    print(f"\nSuccessfully seeded {len(SEEDED_PROMPTS)} items into '{COLLECTION_NAME}' collection!")

if __name__ == "__main__":
    seed()
