#!/usr/bin/env python3
"""
KICKOFF AI Automation System
Generates detailed football news content with AI + live RSS headlines + DALL-E images
"""

import os, json, re, asyncio, aiohttp, xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
HTML_FILE = PROJECT_DIR / "index.html"
IMAGES_DIR = PROJECT_DIR / "images"

RSS_FEEDS = [
    "https://feeds.bbci.co.uk/sport/football/rss.xml",
    "https://www.theguardian.com/football/rss",
]

SLIDER_MARKERS = ("<!--KICKOFF_SLIDER_START-->", "<!--KICKOFF_SLIDER_END-->")
FEATURED_MARKERS = ("<!--KICKOFF_FEATURED_START-->", "<!--KICKOFF_FEATURED_END-->")
STORIES_MARKERS = ("<!--KICKOFF_STORIES_START-->", "<!--KICKOFF_STORIES_END-->")


async def fetch_rss_headlines():
    print("📡 Fetching live RSS headlines...")
    headlines = []
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
        for url in RSS_FEEDS:
            try:
                async with session.get(url, headers={"User-Agent": "KICKOFF-Bot/1.0"}) as resp:
                    if resp.status != 200:
                        continue
                    text = await resp.text()
                    root = ET.fromstring(text)
                    for item in root.iter("item"):
                        title = item.findtext("title", "")
                        if title and len(title) > 20:
                            headlines.append(title.strip())
            except Exception as e:
                print(f"  ⚠ RSS failed for {url}: {e}")
    headlines = list(dict.fromkeys(headlines))[:15]
    print(f"  Got {len(headlines)} headlines")
    return headlines


async def call_openai(messages, api_key, response_format=None, max_tokens=2000, model="gpt-4o-mini"):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    if response_format:
        body["response_format"] = response_format
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers, json=body,
        ) as resp:
            data = await resp.json()
            return data["choices"][0]["message"]["content"]


async def generate_slider_content(api_key, rss_headlines):
    print("  Generating 8-10 stories with importance scores...")
    seed = "\n".join(f"- {h}" for h in rss_headlines[:5]) if rss_headlines else "No live data"
    prompt = f"""You are a football news editor for KICKOFF.
Generate 10 detailed football stories for THE CURRENT TIME: May 12, 2026.
Each story must be VERY specific with real player names, clubs, exact scores, transfer fees from May 2026.

Return ONLY valid JSON array. Each object MUST have:
- headline: specific headline (max 12 words)
- category: league or topic (Premier League, La Liga, Transfers, etc.)
- category_tag: LIVE, BREAKING, EXCLUSIVE, or CONFIRMED
- importance: INTEGER 1-5 (5=most important/breaking, 1=least important)
- image_prompt: UNIQUE scene description - different stadium, different player, different moment

Today's headlines for inspiration:
{seed}

Format: [{{"headline": "...", "category": "...", "category_tag": "...", "importance": 5, "image_prompt": "..."}}, ...]"""
    try:
        text = await call_openai([{"role": "user", "content": prompt}], api_key,
                                  response_format={"type": "json_object"}, max_tokens=1500)
        data = json.loads(text)
        items = data if isinstance(data, list) else data.get("slider", data.get("items", data.get("stories", [])))
        if not isinstance(items, list):
            raise ValueError("not a list")
        for i, item in enumerate(items):
            item.setdefault("headline", f"Slider Story {i+1}")
            item.setdefault("category", "Premier League")
            item.setdefault("category_tag", "LIVE")
            item.setdefault("image_prompt", "Cinematic football stadium at night")
        print(f"    Generated {len(items)} slider stories")
        return items[:4]
    except Exception as e:
        print(f"    ❌ Slider gen failed: {e}")
        return get_fallback_slider()


def get_fallback_slider():
    return [
        {"headline": "Salah hat-trick sinks Manchester United at Anfield", "category": "Premier League",
         "category_tag": "LIVE", "image_prompt": "Mohamed Salah celebrating a hat-trick at Anfield under dramatic floodlights"},
        {"headline": "Real Madrid agree €127M deal for Florian Wirtz", "category": "Transfer Talk",
         "category_tag": "BREAKING", "image_prompt": "Florian Wirtz signing contract at Santiago Bernabeu"},
        {"headline": "Arsenal title hopes crushed by Newcastle smash-and-grab", "category": "Premier League",
         "category_tag": "LIVE", "image_prompt": "Newcastle players celebrating a last-minute winner at St James Park"},
        {"headline": "Barcelona on verge of financial collapse after La Liga rejection", "category": "La Liga",
         "category_tag": "EXCLUSIVE", "image_prompt": "Camp Nou stadium in darkness, moody atmosphere"},
    ]


async def generate_secondary_content(api_key, rss_headlines, count, section_name, examples):
    seed = "\n".join(f"- {h}" for h in rss_headlines[:8]) if rss_headlines else "No live data"
    prompt = f"""You are a football news writer for KICKOFF.
Generate exactly {count} detailed football headlines for the "{section_name}" section.
IMPORTANT: Set all content in THE CURRENT TIME - May 12, 2026.
These should be news happening RIGHT NOW - today's transfers, this week's matches, current rumors.

Each must be VERY specific with: real player names, clubs, exact transfer fees from May 2026, precise match scores.

Real headlines for inspiration:
{seed}

Return ONLY valid JSON array of objects with fields:
- headline: specific detailed headline (max 12 words) about May 2026 events
- category: one of Premier League, La Liga, Serie A, Bundesliga, Ligue 1, Champions League, Transfers, Analysis, Rumors, Opinion, Interviews
- image_prompt: MUST be UNIQUE for each story - describe a DIFFERENT specific scene (different stadiums, different players, different moments)

Examples:
{examples}"""
    try:
        text = await call_openai([{"role": "user", "content": prompt}], api_key,
                                  response_format={"type": "json_object"}, max_tokens=2000)
        data = json.loads(text)
        items = data if isinstance(data, list) else data.get("stories", data.get("items", data.get(section_name, [])))
        if not isinstance(items, list):
            raise ValueError("not a list")
        for i, item in enumerate(items):
            item.setdefault("headline", f"{section_name} Story {i+1}")
            item.setdefault("category", "Premier League")
            item.setdefault("image_prompt", "Cinematic football action shot")
        print(f"    Generated {len(items)} {section_name} stories")
        return items[:count]
    except Exception as e:
        print(f"    ❌ {section_name} gen failed: {e}")
        return []


async def generate_image(api_key, prompt, size, filepath, recraft_key=None, gemini_key=None):
    os.makedirs(IMAGES_DIR, exist_ok=True)
    
    # Priority: Recraft > Gemini > DALL-E
    if recraft_key:
        return await generate_recraft_image(recraft_key, prompt, size, filepath)
    elif gemini_key:
        return await generate_gemini_image(gemini_key, prompt, size, filepath)
    else:
        return await generate_dalle_image(api_key, prompt, size, filepath)


async def generate_gemini_image(gemini_key, prompt, size, filepath):
    """Generate image using Google Gemini API (500 free/day)"""
    import base64
    import random
    
    headers = {
        "Authorization": f"Bearer {gemini_key}",
        "Content-Type": "application/json",
    }
    
    # Size mapping for Gemini
    size_map = {
        "1792x1024": "1792x1024",
        "1024x1024": "1024x1024",
    }
    gemini_size = size_map.get(size, "1024x1024")
    
    # Add unique variation to each prompt so images are different
    unique_variations = [
        "at golden hour with warm sunset lighting",
        "at night with dramatic floodlights and shadows",
        "during a match with crowd in background",
        "in a dramatic stadium tunnel entrance",
        "with dark moody atmosphere and rain effect",
        "under bright midday sun with sharp shadows",
        "at dusk with purple and orange sky",
        "in a filled stadium with dramatic angle",
    ]
    variation = random.choice(unique_variations)
    
    full_prompt = f"{prompt}. Cinematic, photorealistic, {variation}, high contrast, film grain, professional sports photography"
    
    body = {
        "model": "gemini-2.0-flash-exp-image-generation",
        "prompt": full_prompt,
        "output_format": "base64",
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp-image-generation:generateContent",
                headers=headers, json=body,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                if resp.status != 200:
                    err = await resp.text()
                    print(f"    ⚠ Gemini error {resp.status}: {err[:150]}")
                    return None
                data = await resp.json()
                # Extract base64 image
                if "candidates" in data and len(data["candidates"]) > 0:
                    content = data["candidates"][0].get("content", {})
                    parts = content.get("parts", [])
                    for part in parts:
                        if "inlineData" in part:
                            img_data = part["inlineData"]["data"]
                            img_bytes = base64.b64decode(img_data)
                            with open(filepath, "wb") as f:
                                f.write(img_bytes)
                            rel = os.path.relpath(filepath, PROJECT_DIR)
                            print(f"    ✅ Saved: {rel}")
                            return rel
                print(f"    ⚠ Gemini response missing image")
                return None
    except Exception as e:
        print(f"    ❌ Gemini error: {e}")
    return None


async def generate_recraft_image(recraft_key, prompt, size, filepath):
    """Generate image using Recraft API"""
    headers = {
        "Authorization": f"Bearer {recraft_key}",
        "Content-Type": "application/json",
    }
    
    # Map sizes to Recraft dimensions (must be multiples of 32)
    size_map = {
        "1792x1024": {"width": 1792, "height": 1024},
        "1024x1024": {"width": 1024, "height": 1024},
    }
    dimensions = size_map.get(size, {"width": 1024, "height": 1024})
    
    full_prompt = f"{prompt}. Cinematic dark moody aesthetic, dramatic stadium lighting, film print grain, high contrast, professional sports photography, photorealistic, football"
    
    body = {
        "model": "recraft-v3",
        "prompt": full_prompt,
        "image_size": dimensions,
        "style": "realistic_image",
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://external.api.recraft.ai/v1/images/generations",
                headers=headers, json=body,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                if resp.status != 200:
                    err = await resp.text()
                    print(f"    ⚠ Recraft error {resp.status}: {err[:100]}")
                    return None
                data = await resp.json()
                # Recraft returns base64 or URL
                if data.get("images") and len(data["images"]) > 0:
                    image_data = data["images"][0]
                    if isinstance(image_data, dict):
                        # URL returned
                        if "url" in image_data:
                            image_url = image_data["url"]
                        elif "base64" in image_data:
                            # Base64 - decode and save directly
                            import base64
                            img_bytes = base64.b64decode(image_data["base64"])
                            with open(filepath, "wb") as f:
                                f.write(img_bytes)
                            rel = os.path.relpath(filepath, PROJECT_DIR)
                            print(f"    ✅ Saved: {rel}")
                            return rel
                    return None
                print(f"    ⚠ Recraft response missing images")
                return None
    except Exception as e:
        print(f"    ❌ Recraft error: {e}")
    return None


async def generate_dalle_image(api_key, prompt, size, filepath):
    """Generate image using DALL-E (fallback)"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    full_prompt = f"{prompt}. Cinematic dark moody aesthetic, dramatic stadium lighting, film print grain, high contrast, professional sports photography, photorealistic"
    body = {
        "model": "dall-e-3",
        "prompt": full_prompt,
        "size": size,
        "quality": "standard",
        "n": 1,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.openai.com/v1/images/generations",
                headers=headers, json=body,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                if resp.status != 200:
                    err = await resp.text()
                    print(f"    ⚠ DALL-E error {resp.status}: {err[:100]}")
                    return None
                data = await resp.json()
                image_url = data["data"][0]["url"]
            async with session.get(image_url, timeout=aiohttp.ClientTimeout(total=60)) as img_resp:
                if img_resp.status == 200:
                    with open(filepath, "wb") as f:
                        f.write(await img_resp.read())
                    rel = os.path.relpath(filepath, PROJECT_DIR)
                    print(f"    ✅ Saved: {rel}")
                    return rel
    except Exception as e:
        print(f"    ❌ Image error: {e}")
    return None


def format_times_ago(count):
    minutes = [15, 28, 42, 55]
    hours = [1, 2, 3, 4, 5, 6]
    times = [f"{m} min ago" for m in minutes] + [f"{h} hour ago" for h in hours]
    return times[:count]


def build_slider_html(items, images):
    html = ""
    for item in items:
        img_src = images.get(item.get("_key", ""), "")
        cat = item.get("category", "Premier League")
        tag = item.get("category_tag", "LIVE")
        headline = item.get("headline", "Football News")
        html += f"""            <div class="slide">
                <div class="slide-image">
                    <img src="{img_src}" alt="{cat}">
                </div>
                <div class="slide-content">
                    <div class="slide-meta"><span style="color:#0e8a46">● {tag}</span> · {cat}</div>
                    <h3 class="slide-title">{headline}</h3>
                </div>
            </div>
"""
    return html


def build_featured_html(items, images):
    html = ""
    for item in items:
        img_src = images.get(item.get("_key", ""), "")
        cat = item.get("category", "Premier League")
        headline = item.get("headline", "Football News")
        html += f"""            <a href="#" class="featured-card">
                <div class="featured-image">
                    <img src="{img_src}" style="width:100%;height:100%;object-fit:cover;">
                </div>
                <div class="featured-meta" data-cat="{cat}">{cat} · LIVE</div>
                <h3 class="featured-title">{headline}</h3>
            </a>
"""
    return html


def build_stories_html(items, images):
    times = format_times_ago(len(items))
    html = ""
    for i, item in enumerate(items):
        img_src = images.get(item.get("_key", ""), "")
        cat = item.get("category", "Premier League")
        headline = item.get("headline", "Football News")
        time_str = times[i] if i < len(times) else f"{i+1} hour ago"
        html += f"""            <a href="#" class="pub-card">
                <div class="pub-image"><img src="{img_src}" style="width:100%;height:100%;object-fit:cover;"></div>
                <div class="pub-meta" data-cat="{cat}">{cat} · {time_str}</div>
                <h3 class="pub-title">{headline}</h3>
            </a>
"""
    return html


def replace_between(text, markers, new_content):
    start_marker, end_marker = markers
    start_idx = text.find(start_marker)
    end_idx = text.find(end_marker)
    if start_idx == -1 or end_idx == -1:
        print(f"  ⚠ Marker not found: {start_marker}")
        return text
    start_idx += len(start_marker)
    before = text[:start_idx]
    after = text[end_idx:]
    return before + "\n" + new_content + after


async def run():
    print("=" * 60)
    print("⚡ KICKOFF AI AUTOMATION SYSTEM")
    print("=" * 60)

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        # Try config file
        config_file = PROJECT_DIR / "config.json"
        if config_file.exists():
            with open(config_file) as f:
                cfg = json.load(f)
                api_key = cfg.get("api_keys", {}).get("openai", "")
    
    if not api_key or api_key == "your-openai-api-key-here":
        print("❌ No valid OpenAI API key found. Set OPENAI_API_KEY env var or update config.json")
        return

    # 1. Fetch live RSS headlines
    rss_headlines = await fetch_rss_headlines()

    # 2. Generate content with importance scoring
    print("\n📝 Generating content with importance scoring...")
    
    # Generate 10 stories with importance scores (1-5)
    all_stories = await generate_slider_content(api_key, rss_headlines)
    
    # Ensure each story has an importance score
    for story in all_stories:
        if "importance" not in story:
            story["importance"] = 3  # Default medium importance
    
    # Sort by importance (highest first)
    all_stories.sort(key=lambda x: x.get("importance", 3), reverse=True)
    
    # Assign to sections based on importance
    slider_items = all_stories[:4]  # Top 4 most important
    featured_items = all_stories[4:7]  # Next 3
    stories_items = all_stories[7:]  # Rest
    
    # Add section-specific tags based on importance
    for i, item in enumerate(slider_items):
        item["category_tag"] = "BREAKING" if item.get("importance", 3) >= 5 else "LIVE"
    for item in featured_items:
        item["category_tag"] = "FEATURED"
    for item in stories_items:
        item["category_tag"] = "NEWS"
    
    print(f"    📊 Priority assignment:")
    print(f"       🔴 Slider (top 4): {[s.get('importance', 3) for s in slider_items]}")
    print(f"       🟠 Featured (3): {[s.get('importance', 3) for s in featured_items]}")
    print(f"       🟢 Stories ({len(stories_items)}): {[s.get('importance', 3) for s in stories_items]}")
    
    # Generate images for each story
    """Generate image using Google Gemini API (500 free/day) - 4:3 ratio"""
    import base64
    import random
    
    headers = {
        "Authorization": f"Bearer {gemini_key}",
        "Content-Type": "application/json",
    }
    
    # ALL IMAGES AT 4:3 RATIO - will be cropped/resized by CSS
    gemini_size = "1024x768"  # 4:3 ratio
    
    # Add unique variation to each prompt so images are different
    unique_variations = [
        "at golden hour with warm sunset lighting",
        "at night with dramatic floodlights and shadows", 
        "during a match with crowd in background",
        "in a dramatic stadium tunnel entrance",
        "with dark moody atmosphere and rain effect",
        "under bright midday sun with sharp shadows",
        "at dusk with purple and orange sky",
        "in a filled stadium with dramatic angle",
        "training ground session with players",
        "press conference room with manager",
        "medical room with player recovering",
        "training ground gym with equipment",
    ]
    variation = random.choice(unique_variations)
    
    full_prompt = f"{prompt}. Cinematic, photorealistic, {variation}, high contrast, film grain, professional sports photography"
    
    body = {
        "model": "gemini-2.0-flash-exp-image-generation",
        "prompt": full_prompt,
        "output_format": "base64",
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp-image-generation:generateContent",
                headers=headers, json=body,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                if resp.status != 200:
                    err = await resp.text()
                    print(f"    ⚠ Gemini error {resp.status}: {err[:150]}")
                    return None
                data = await resp.json()
                if "candidates" in data and len(data["candidates"]) > 0:
                    content = data["candidates"][0].get("content", {})
                    parts = content.get("parts", [])
                    for part in parts:
                        if "inlineData" in part:
                            img_data = part["inlineData"]["data"]
                            img_bytes = base64.b64decode(img_data)
                            with open(filepath, "wb") as f:
                                f.write(img_bytes)
                            rel = os.path.relpath(filepath, PROJECT_DIR)
                            print(f"    ✅ Saved: {rel}")
                            return rel
                print(f"    ⚠ Gemini response missing image")
                return None
    except Exception as e:
        print(f"    ❌ Gemini error: {e}")
    return None


# Check for Recraft or Gemini API keys first
    recraft_key = os.environ.get("RECRAFT_API_KEY", "")
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    
    if not recraft_key:
        config_file = PROJECT_DIR / "config.json"
        if config_file.exists():
            with open(config_file) as f:
                cfg = json.load(f)
                recraft_key = cfg.get("api_keys", {}).get("recraft", "")
                if not gemini_key:
                    gemini_key = cfg.get("api_keys", {}).get("gemini", "")
    
    # Debug: show what's available
    print(f"\n🔑 API Keys status:")
    print(f"   OpenAI (DALL-E): {'✓' if api_key and api_key != 'your-openai-api-key-here' else '✗'}")
    print(f"   Recraft: {'✓' if recraft_key else '✗'}")
    print(f"   Gemini: {'✓' if gemini_key else '✗'}")
    
    if recraft_key:
        print("  → Using Recraft API for image generation")
    elif gemini_key:
        print("  → Using Google Gemini API (500 free/day)")
    elif api_key:
        print("  → Using DALL-E for image generation (fallback)")
    
    # 3. Add keys for image mapping
    all_items = []
    for prefix, items in [("slider", slider_items), ("featured", featured_items), ("story", stories_items)]:
        for i, item in enumerate(items):
            item["_key"] = f"{prefix}_{i}"
            all_items.append(item)

    print(f"\n🎨 Generating {len(all_items)} images (all 4:3 ratio)...")
    image_map = {}

    for item in all_items:
        key = item["_key"]
        # ALL IMAGES AT 4:3 RATIO - CSS will crop/resize as needed
        size = "1024x768"  # 4:3 aspect ratio
        filename = f"{key}.png"
        filepath = IMAGES_DIR / filename
        rel = await generate_image(api_key, item["image_prompt"], size, filepath, recraft_key, gemini_key)
        if rel:
            image_map[key] = rel
        else:
            # Fallback to Unsplash placeholders
            image_map[key] = f"https://images.unsplash.com/photo-1511882150382-421056c89033?w=1024&h=768&fit=crop"

    # 4. Update HTML
    print("\n🌐 Updating website...")
    with open(HTML_FILE, "r") as f:
        html = f.read()

    slider_html = build_slider_html(slider_items, image_map)
    html = replace_between(html, SLIDER_MARKERS, slider_html)

    featured_html = build_featured_html(featured_items, image_map)
    html = replace_between(html, FEATURED_MARKERS, featured_html)

    stories_html = build_stories_html(stories_items, image_map)
    html = replace_between(html, STORIES_MARKERS, stories_html)

    with open(HTML_FILE, "w") as f:
        f.write(html)

    print("✅ Website updated!")

    # 5. Save content data
    content_data = {
        "generated_at": datetime.now().isoformat(),
        "rss_headlines_used": len(rss_headlines),
        "sections": {
            "slider": slider_items,
            "featured": featured_items,
            "stories": stories_items,
        },
    }
    with open(PROJECT_DIR / "content_data.json", "w") as f:
        json.dump(content_data, f, indent=2)

    print("\n" + "=" * 60)
    print("✅ Automation complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run())
