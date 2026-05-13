#!/usr/bin/env python3
"""
KICKOFF AI Automation System
Generates detailed football news content with AI + live RSS headlines + DALL-E images
"""

import os
import json
import re
import asyncio
import aiohttp
import xml.etree.ElementTree as ET
import ssl
from datetime import datetime, timedelta
from pathlib import Path

# Fix SSL certificate issue on macOS
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

PROJECT_DIR = Path(__file__).parent
HTML_FILE = PROJECT_DIR / "index.html"
IMAGES_DIR = PROJECT_DIR / "images"

RSS_FEEDS = [
    # Tier 1 - Major Established Media
    "https://feeds.bbci.co.uk/sport/football/rss.xml",
    "https://www.theguardian.com/football/rss",
    "https://www.skysports.com/rss/12040",
    "https://www.espn.com/espn/rss/news",
    # Tier 2 - Established Football Media
    "https://www.goal.com/en-us/rss/news",
    "https://www.tribalfootball.com/rss",
    "https://www.football365.com/rss",
    # Tier 3 - Popular Sports Blogs
    "https://www.planetfootball.com/feed",
    "https://www.footballinsider247.com/feed",
]

SLIDER_MARKERS = ("<!--KICKOFF_SLIDER_START-->", "<!--KICKOFF_SLIDER_END-->")
FEATURED_MARKERS = ("<!--KICKOFF_FEATURED_START-->", "<!--KICKOFF_FEATURED_END-->")
STORIES_MARKERS = ("<!--KICKOFF_STORIES_START-->", "<!--KICKOFF_STORIES_END-->")


async def fetch_rss_headlines():
    print("📡 Fetching live RSS headlines from trusted sources...")
    articles = []
    # Create SSL context that doesn't verify certificates (for macOS)
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=20)) as session:
        for url in RSS_FEEDS:
            source = url.split("//")[1].split("/")[0] if "//" in url else "unknown"
            try:
                async with session.get(url, headers={"User-Agent": "KICKOFF-Bot/1.0"}) as resp:
                    if resp.status != 200:
                        continue
                    text = await resp.text()
                    root = ET.fromstring(text)
                    for item in root.iter("item"):
                        title = item.findtext("title", "").strip()
                        desc = item.findtext("description", "").strip()
                        link = item.findtext("link", "").strip()
                        if title and len(title) > 15:
                            clean_desc = re.sub(r'<[^>]+>', '', desc)[:200] if desc else ""
                            articles.append({
                                "title": title,
                                "description": clean_desc,
                                "source": source,
                                "link": link
                            })
            except Exception as e:
                print(f"  ⚠ {source} failed: {e}")
    
    # Deduplicate by title similarity
    seen = set()
    unique_articles = []
    for art in articles:
        title_lower = art["title"].lower()
        if title_lower not in seen:
            seen.add(title_lower)
            unique_articles.append(art)
    
    unique_articles = unique_articles[:15]
    print(f"  ✅ Got {len(unique_articles)} unique articles from {len(set(a['source'] for a in unique_articles))} sources")
    return unique_articles


def extract_json_from_text(text):
    """Extract JSON array or object from text that may contain markdown or explanations"""
    import re
    # Try to find JSON array
    match = re.search(r'\[[\s\S]*\]', text)
    if match:
        return match.group(0)
    # Try to find JSON object
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        return match.group(0)
    return text


async def call_ollama(messages, model="llama3.2", max_tokens=2000):
    """Use Ollama for local AI generation (free, private)"""
    import aiohttp
    
    print(f"    🤖 Calling Ollama ({model})...")
    
    # Convert messages to Ollama format
    system = ""
    user_content = ""
    for msg in messages:
        if msg["role"] == "system":
            system = msg["content"]
        elif msg["role"] == "user":
            user_content = msg["content"]
    
    prompt = f"{system}\n\n{user_content}" if system else user_content
    
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": max_tokens,
            "temperature": 0.7,
        }
    }
    
    try:
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(
                "http://localhost:11434/api/generate",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=180),
            ) as resp:
                if resp.status != 200:
                    err = await resp.text()
                    print(f"  ⚠ Ollama error {resp.status}: {err[:200]}")
                    return "[]"
                data = await resp.json()
                response = data.get("response", "")
                print(f"    ✅ Ollama response: {response[:100]}...")
                return response
    except Exception as e:
        print(f"  ⚠ Ollama error: {e}")
        return "[]"


async def call_openai(messages, api_key, response_format=None, max_tokens=2000, model="gpt-4o-mini"):
    # First try Ollama (local, free)
    try:
        result = await call_ollama(messages, model="llama3.2", max_tokens=max_tokens)
        if result and result != "[]":
            # Extract JSON from the response (Ollama may add explanation text)
            return extract_json_from_text(result)
    except Exception as e:
        print(f"    ⚠ Ollama failed: {e}")
    
    # If Ollama fails, try cloud APIs
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if not gemini_key:
        config_file = PROJECT_DIR / "config.json"
        if config_file.exists():
            with open(config_file) as f:
                cfg = json.load(f)
                gemini_key = cfg.get("api_keys", {}).get("gemini", "")
    
    if gemini_key:
        return await call_gemini(messages, gemini_key, response_format, max_tokens)
    
    # Fall back to OpenAI if no Gemini key
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
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
        async with session.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers, json=body,
        ) as resp:
            data = await resp.json()
            return data["choices"][0]["message"]["content"]


async def call_gemini(messages, gemini_key, response_format=None, max_tokens=2000):
    """Use Gemini for text generation"""
    import json
    
    # Convert messages format for Gemini
    user_msg = messages[-1]["content"] if messages else ""
    
    headers = {
        "Content-Type": "application/json",
    }
    
    body = {
        "contents": [{"parts": [{"text": user_msg}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": max_tokens,
        }
    }
    
    try:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            async with session.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}",
                headers=headers, json=body,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                if resp.status != 200:
                    err = await resp.text()
                    print(f"  ⚠ Gemini text error {resp.status}: {err[:100]}")
                    return "[]"
                data = await resp.json()
                if "candidates" in data and len(data["candidates"]) > 0:
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    # Extract JSON from response if wrapped in text
                    try:
                        # Try to find JSON in the response
                        import re
                        json_match = re.search(r'\[.*\]', text, re.DOTALL)
                        if json_match:
                            return json_match.group(0)
                        return text
                    except:
                        return text
                return "[]"
    except Exception as e:
        print(f"  ⚠ Gemini text error: {e}")
        return "[]"


async def generate_slider_content(api_key, rss_articles):
    """Transform real RSS articles into KICKOFF's style"""
    print("  🎨 Transforming real articles into KICKOFF style...")
    
    if not rss_articles or len(rss_articles) < 4:
        print("    ⚠ Not enough RSS articles, using fallback")
        return get_fallback_slider()
    
    # Format articles for AI transformation
    articles_text = "\n\n".join([
        f"Source: {a.get('source', 'Unknown')}\nHeadline: {a.get('title', '')}\nSummary: {a.get('description', '')}"
        for a in rss_articles[:10]
    ])
    
    prompt = f"""You are KICKOFF's football news editor. Transform the real headlines below into KICKOFF's signature style.

KICKOFF STYLE:
- Short, punchy headlines (max 12 words) - dramatic, urgent, like breaking news
- Bold, attention-grabbing but accurate
- Categories: Premier League, La Liga, Transfers, Champions League, Serie A, Bundesliga
- Tags: LIVE, BREAKING, EXCLUSIVE, CONFIRMED
- Add importance score (1-5, 5=most breaking)

YOUR JOB:
- Transform the real headlines below into KICKOFF style
- Keep the core facts accurate (same players, teams, events)
- Add drama/urgency while staying truthful
- Generate a unique image_prompt for each story

REAL ARTICLES FROM TRUSTED SOURCES:
{articles_text}

Return ONLY valid JSON array with keys:
- original_headline: the original RSS headline
- headline: KICKOFF-style transformed headline (max 12 words)
- category: Premier League, La Liga, Transfers, Champions League, etc.
- category_tag: LIVE, BREAKING, EXCLUSIVE, or CONFIRMED
- importance: INTEGER 1-5 (5=most breaking/important)
- image_prompt: Unique visual description for AI image generation
- source: the original source (BBC, Sky, Guardian, etc.)

Format: [{{"original_headline": "...", "headline": "...", "category": "...", "category_tag": "...", "importance": 5, "image_prompt": "...", "source": "..."}}, ...]"""
    
    try:
        text = await call_openai([{"role": "user", "content": prompt}], api_key,
                                  response_format={"type": "json_object"}, max_tokens=2000)
        data = json.loads(text)
        items = data if isinstance(data, list) else data.get("slider", data.get("items", []))
        if not isinstance(items, list):
            raise ValueError("not a list")
        
        # Ensure all required fields
        for i, item in enumerate(items):
            item.setdefault("headline", item.get("original_headline", f"Story {i+1}")[:60])
            item.setdefault("category", "Premier League")
            item.setdefault("category_tag", "LIVE")
            item.setdefault("importance", 3)
            item.setdefault("image_prompt", "Cinematic football stadium at night with dramatic lighting")
            item.setdefault("source", "RSS")
        
        print(f"    ✅ Transformed {len(items)} real articles into KICKOFF style")
        return items[:10]
    except Exception as e:
        print(f"    ❌ Transformation failed: {e}")
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


async def generate_subnp_image(prompt, size, filepath):
    """Generate image using SubNP free API"""
    import urllib.request
    import urllib.parse
    import json
    import ssl
    
    # Create unverified SSL context for macOS
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    urls = [
        "https://subnp.com/api/free/generate",
        "https://api.subnp.com/v1/generate",
    ]
    
    full_prompt = f"{prompt}. Cinematic, photorealistic, high quality, football, dramatic lighting"
    
    for url in urls:
        try:
            payload = json.dumps({"prompt": full_prompt, "model": "turbo"}).encode()
            req = urllib.request.Request(url, data=payload, method="POST")
            req.add_header("Content-Type", "application/json")
            
            with urllib.request.urlopen(req, context=ssl_context, timeout=120) as response:
                result = response.read()
                result_json = json.loads(result.decode())
                
                if result_json.get("success") and result_json.get("image_url"):
                    image_url = result_json["image_url"]
                    with urllib.request.urlopen(image_url, context=ssl_context, timeout=60) as img_response:
                        with open(filepath, "wb") as f:
                            f.write(img_response.read())
                    rel = os.path.relpath(filepath, PROJECT_DIR)
                    print(f"    ✅ Saved: {rel}")
                    return rel
        except Exception as e:
            print(f"    ⚠ SubNP ({url}): {str(e)[:60]}")
            continue
    
    return None


async def generate_image(api_key, prompt, size, filepath, recraft_key=None, gemini_key=None):
    os.makedirs(IMAGES_DIR, exist_ok=True)
    
    # Try SubNP first (free, no key needed)
    print(f"    🎨 Generating image with SubNP...")
    result = await generate_subnp_image(prompt, size, filepath)
    if result:
        return result
    
    # Try Gemini (500 free/day)
    if gemini_key:
        result = await generate_gemini_image(gemini_key, prompt, size, filepath)
        if result:
            return result
    
    # Try DALL-E as fallback
    if api_key:
        return await generate_dalle_image(api_key, prompt, size, filepath)
    
    return None





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
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
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
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
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
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
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


# Fallback content when API quota is exceeded
FALLBACK_CONTENT = [
    {"headline": "Premier League title race reaches thrilling climax with 3 teams in contention", "category": "Premier League", "importance": 5, "image_prompt": "Premier League trophy at stadium", "category_tag": "BREAKING"},
    {"headline": "Real Madrid complete €120M signing of generational talent", "category": "Transfers", "importance": 5, "image_prompt": "Player signing contract at Bernabeu", "category_tag": "BREAKING"},
    {"headline": "Champions League final: Tactical preview and key battles to watch", "category": "Champions League", "importance": 4, "image_prompt": "Champions League trophy in stadium", "category_tag": "FEATURED"},
    {"headline": "Barcelona's youth academy produces next generational superstar", "category": "La Liga", "importance": 4, "image_prompt": "Young player training at La Masia", "category_tag": "FEATURED"},
    {"headline": "Bayern Munich secure domestic double with dominant display", "category": "Bundesliga", "importance": 4, "image_prompt": "Bayern Munich celebration", "category_tag": "FEATURED"},
    {"headline": "Inter Milan announce ambitious expansion plans for stadium", "category": "Serie A", "importance": 3, "image_prompt": "San Siro stadium", "category_tag": "NEWS"},
    {"headline": "PSG's new project aims to build around homegrown talent", "category": "Ligue 1", "importance": 3, "image_prompt": "PSG stadium", "category_tag": "NEWS"},
    {"headline": "Rising star reveals childhood dream of playing for hometown club", "category": "Interviews", "importance": 2, "image_prompt": "Player interview", "category_tag": "NEWS"},
    {"headline": "VAR controversy sparks debate among managers and fans", "category": "Analysis", "importance": 2, "image_prompt": "VAR monitor", "category_tag": "NEWS"},
    {"headline": "Football legends gather for annual charity match event", "category": "Opinion", "importance": 1, "image_prompt": "Charity football match", "category_tag": "NEWS"},
]

FALLBACK_IMAGES = [
    "https://images.unsplash.com/photo-1511882150382-421056c89033?w=1024&h=768&fit=crop",
    "https://images.unsplash.com/photo-1574629810360-7efbbe195018?w=1024&h=768&fit=crop",
    "https://images.unsplash.com/photo-1431324155629-1a6deb1dec8d?w=1024&h=768&fit=crop",
    "https://images.unsplash.com/photo-1579952363873-27f3bade9f55?w=1024&h=768&fit=crop",
    "https://images.unsplash.com/photo-1489944440615-453fc2b6a9a9?w=1024&h=768&fit=crop",
    "https://images.unsplash.com/photo-1626249021446-6986b5d71bc5?w=1024&h=768&fit=crop",
    "https://images.unsplash.com/photo-1517466787929-bc90951d0974?w=1024&h=768&fit=crop",
    "https://images.unsplash.com/photo-1575361204480-aadea25e6e68?w=1024&h=768&fit=crop",
    "https://images.unsplash.com/photo-1606925797300-0b35e9d1794e?w=1024&h=768&fit=crop",
    "https://images.unsplash.com/photo-1540747913346-19e32dc3e97e?w=1024&h=768&fit=crop",
]


def build_slider_html(items, images):
    html = ""
    for i, item in enumerate(items):
        img_src = images.get(item.get("_key", ""), "")
        cat = item.get("category", "Premier League")
        tag = item.get("category_tag", "LIVE")
        headline = item.get("headline", "Football News").replace("**", "")
        html += f"""            <a href="posts/post_{i}.html" class="slide">
                <div class="slide-image">
                    <img src="{img_src}" alt="{cat}">
                </div>
                <div class="slide-content">
                    <div class="slide-meta"><span style="color:#0e8a46">● {tag}</span> · {cat}</div>
                    <h3 class="slide-title">{headline}</h3>
                </div>
            </a>
"""
    return html


def build_featured_html(items, images):
    html = ""
    for i, item in enumerate(items):
        img_src = images.get(item.get("_key", ""), "")
        cat = item.get("category", "Premier League")
        headline = item.get("headline", "Football News").replace("**", "")
        html += f"""            <a href="posts/post_{i + 4}.html" class="featured-card">
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
        headline = item.get("headline", "Football News").replace("**", "")
        time_str = times[i] if i < len(times) else f"{i+1} hour ago"
        html += f"""            <a href="posts/post_{i + 7}.html" class="pub-card">
                <div class="pub-image"><img src="{img_src}" style="width:100%;height:100%;object-fit:cover;"></div>
                <div class="pub-meta" data-cat="{cat}">{cat} · {time_str}</div>
                <h3 class="pub-title">{headline}</h3>
            </a>
"""
    return html


def generate_post_html(item, image_url, content):
    """Generate individual post page"""
    post_template = PROJECT_DIR / "post.html"
    if not post_template.exists():
        return None
    
    with open(post_template, "r") as f:
        html = f.read()
    
    # Replace placeholders
    headline = item.get("headline", "Football News").replace("**", "")
    category = item.get("category", "Premier League")
    tag = item.get("category_tag", "LIVE")
    time_str = "Just now"
    
    html = html.replace("POST_HEADLINE", headline)
    html = html.replace("POST_CATEGORY", category)
    html = html.replace("POST_TAG", tag)
    html = html.replace("POST_TIME", time_str)
    html = html.replace("POST_CONTENT", content)
    html = html.replace("POST_HERO_IMAGE", image_url if image_url else FALLBACK_IMAGES[0])
    
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

    # Get API keys
    api_key = os.environ.get("OPENAI_API_KEY", "")
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    
    if not api_key:
        config_file = PROJECT_DIR / "config.json"
        if config_file.exists():
            with open(config_file) as f:
                cfg = json.load(f)
                api_key = cfg.get("api_keys", {}).get("openai", "")
                if not gemini_key:
                    gemini_key = cfg.get("api_keys", {}).get("gemini", "")
    
    # Check available keys
    print(f"\n🔑 API Keys status:")
    print(f"   OpenAI (DALL-E): {'✓' if api_key and api_key != 'your-openai-api-key-here' else '✗'}")
    print(f"   Gemini (text+images): {'✓' if gemini_key else '✗'}")
    
    # If no OpenAI key, we can still use Gemini for both text and images
    
    # 1. Fetch live RSS headlines
    rss_headlines = await fetch_rss_headlines()

    # 2. Generate content with importance scoring
    print("\n📝 Generating content with importance scoring...")
    
    # Generate 10 stories with importance scores (1-5)
    all_stories = await generate_slider_content(api_key, rss_headlines)
    
    # If API failed/quota exceeded, use fallback content
    if not all_stories:
        print("  ⚠ API quota exceeded, using fallback content")
        all_stories = FALLBACK_CONTENT.copy()
    
    # Ensure each story has an importance score
    for story in all_stories:
        if "importance" not in story:
            story["importance"] = 3
    
    # Sort by importance (highest first)
    all_stories.sort(key=lambda x: x.get("importance", 3), reverse=True)
    
    # Assign to sections based on importance
    slider_items = all_stories[:4]
    featured_items = all_stories[4:7]
    stories_items = all_stories[7:]
    
    # Add section-specific tags
    for item in slider_items:
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
    
    # Note: Puter is tried first (free), then Gemini, then DALL-E
    if recraft_key:
        print("  → Recraft available as backup")
    if gemini_key:
        print("  → Gemini available as backup")
    if api_key:
        print("  → DALL-E available as backup")
    
    # 3. Add keys for image mapping
    all_items = []
    for prefix, items in [("slider", slider_items), ("featured", featured_items), ("story", stories_items)]:
        for i, item in enumerate(items):
            item["_key"] = f"{prefix}_{i}"
            all_items.append(item)

    print(f"\n🎨 Generating {len(all_items)} images (all 4:3 ratio)...")
    image_map = {}

    for i, item in enumerate(all_items):
        key = item["_key"]
        size = "1024x768"  # 4:3 aspect ratio
        filename = f"{key}.png"
        filepath = IMAGES_DIR / filename
        rel = await generate_image(api_key, item["image_prompt"], size, filepath, recraft_key, gemini_key)
        if rel:
            image_map[key] = rel
        else:
            # Use fallback images - cycle through them
            fallback_img = FALLBACK_IMAGES[i % len(FALLBACK_IMAGES)]
            image_map[key] = fallback_img

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

    # 4b. Generate individual post pages
    print("📝 Generating post pages...")
    all_items = slider_items + featured_items + stories_items
    for i, item in enumerate(all_items):
        post_id = f"post_{i}"
        image_key = item.get("_key", "")
        image_url = image_map.get(image_key, FALLBACK_IMAGES[0])
        
        # Generate simple content for the post
        headline = item.get("headline", "Football News").replace("**", "")
        category = item.get("category", "Premier League")
        content = f"""
        <p>{headline}</p>
        <p>This is a developing story. {category} continues to make headlines as the season progresses.</p>
        <p>Stay tuned to KICKOFF for the latest updates on this story and more football news.</p>
        """
        
        post_html = generate_post_html(item, image_url, content)
        if post_html:
            post_file = PROJECT_DIR / "posts" / f"{post_id}.html"
            os.makedirs(PROJECT_DIR / "posts", exist_ok=True)
            with open(post_file, "w") as f:
                f.write(post_html)
    
    print(f"   ✅ Generated {len(all_items)} post pages")

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

    print("\n📤 Pushing to GitHub...")
    import subprocess
    try:
        subprocess.run(["git", "add", "-A"], cwd=PROJECT_DIR, check=True)
        subprocess.run(["git", "commit", "-m", f"Auto-update: {datetime.now().strftime('%Y-%m-%d %H:%M')}"], cwd=PROJECT_DIR, check=True)
        subprocess.run(["git", "push"], cwd=PROJECT_DIR, check=True)
        print("   ✅ Pushed to GitHub")
    except Exception as e:
        print(f"   ⚠ Git push failed: {e}")

    print("\n" + "=" * 60)
    print("✅ Automation complete!")
    print("=" * 60)


def ensure_ollama_running():
    """Start Ollama if not already running"""
    import subprocess
    import socket
    
    # Check if Ollama is already running
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', 11434))
    sock.close()
    
    if result != 0:
        print("🔄 Starting Ollama...")
        subprocess.Popen(["ollama", "serve"], 
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL)
        import time
        time.sleep(3)
        print("   ✅ Ollama started")


if __name__ == "__main__":
    ensure_ollama_running()
    asyncio.run(run())
