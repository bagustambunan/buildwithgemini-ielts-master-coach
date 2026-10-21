import os
import time
import subprocess
from playwright.sync_api import sync_playwright

output_dir = "/tmp/demo_recordings"
os.makedirs(output_dir, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
    )
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        record_video_dir=output_dir,
        record_video_size={"width": 1280, "height": 720}
    )
    page = context.new_page()
    page.goto("http://localhost:8081", wait_until="networkidle")
    page.wait_for_selector("#input")
    time.sleep(2)

    def send_chat_message(prompt_text):
        input_el = page.locator("#input")
        input_el.click()
        input_el.fill("")
        for char in prompt_text:
            input_el.type(char, delay=25)
        time.sleep(0.5)
        page.keyboard.press("Enter")
        
        # Wait for agent response
        time.sleep(2)
        page.wait_for_function(
            "() => { const bubbles = document.querySelectorAll('.msg.agent .bubble'); return bubbles.length > 0 && bubbles[bubbles.length - 1].textContent !== '…'; }",
            timeout=120000
        )
        time.sleep(2)
        page.evaluate("() => { const log = document.getElementById('log'); log.scrollTop = log.scrollHeight; }")

    print("Step 1: Speaking Cue Card Prompt...")
    send_chat_message("Saya ingin latihan Speaking Part 2 tentang teknologi yang mempermudah hidup. Berikan cue card lengkap dan kosakata akademis.")
    time.sleep(6)

    print("Step 2: Visual Task 1 Chart Generation...")
    send_chat_message("Generate grafik bar chart Task 1 tentang perbandingan konsumsi Renewable Energy di 4 negara Eropa tahun 2010 vs 2025")
    time.sleep(7)

    print("Step 3: Cambridge Band Calculator & Diagnostics...")
    send_chat_message("Hitung overall band IELTS saya jika L=7.5, R=7.0, W=6.0, S=6.5 dan jelaskan skill mana yang jadi prioritas.")
    time.sleep(6)

    # Smooth scroll review
    page.evaluate("() => { const log = document.getElementById('log'); log.scrollTop = 0; }")
    time.sleep(2)
    page.evaluate("() => { const log = document.getElementById('log'); log.scrollTo({top: log.scrollHeight, behavior: 'smooth'}); }")
    time.sleep(4)

    video_path = page.video.path()
    context.close()
    browser.close()

print(f"Recorded raw video at: {video_path}")

mp4_dest = "/config/Desktop/BuildWithGemini/ielts-master-coach/demo_video.mp4"
artifact_dest = "/config/.gemini/antigravity/brain/1be8a6bf-26cc-4ba2-bc1a-809fec1be58f/demo_video.mp4"

subprocess.run([
    "ffmpeg", "-y", "-i", video_path,
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
    mp4_dest
], check=True)

subprocess.run(["cp", mp4_dest, artifact_dest], check=True)
print(f"Demo video saved to:\n  - {mp4_dest}\n  - {artifact_dest}")
