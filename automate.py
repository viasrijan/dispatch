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
import hashlib
from pathlib import Path

# Fix SSL certificate issue on macOS
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# Settings
GENERATE_POST_PAGES = True  # Generate individual post pages
AUTO_PUSH = True  # Push to GitHub automatically

# Image API Keys
PEXELS_API_KEY = "uojC04iqYEDXYiuAzMNEOW4KFKzZz514yGjfa6cGPpc98d9jkFfOCrM9"
PIXABAY_API_KEY = "55840135-74cfba926282eebc8e1950565"
MAGNIFIC_API_KEY = "FPSX2443565dd2c548989f13fb2be2758124"

# Football image search queries
FOOTBALL_QUERIES = [
    "football stadium",
    "soccer match",
    "premier league",
    "football player",
    "football game",
    "soccer stadium",
    "football crowd",
    "football goal",
]

# Tag System (24 tags across 4 tiers)
TAG_CONTINENTS = ["Europe", "South America", "North America", "Asia", "Africa", "Oceania"]
TAG_LEAGUES = ["Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1"]
TAG_COMPETITIONS = ["Champions League", "Europa League", "FA Cup", "World Cup", "European Championship", "Copa America"]
TAG_CONTENT_TYPES = ["Transfers", "Rumors", "Interviews", "Analysis", "Opinion", "Match Reports", "Stats"]

TAG_MAP = {
    # League -> Continent mapping
    "Premier League": ["Europe"],
    "La Liga": ["Europe"],
    "Serie A": ["Europe"],
    "Bundesliga": ["Europe"],
    "Ligue 1": ["Europe"],
    # Competition -> Continent mapping
    "Champions League": ["Europe"],
    "Europa League": ["Europe"],
    "FA Cup": ["Europe"],
    "World Cup": ["Europe", "South America", "North America", "Asia", "Africa", "Oceania"],
    "European Championship": ["Europe"],
    "Copa America": ["South America"],
}

def get_tags_for_category(category, content_type="Match Reports"):
    """Get all applicable tags for a post based on category"""
    tags = []
    
    # Add content type tag
    if content_type in TAG_CONTENT_TYPES:
        tags.append(content_type)
    
    # Add league tags and their parent continents
    if category in TAG_LEAGUES:
        tags.append(category)
        if category in TAG_MAP:
            tags.extend(TAG_MAP[category])
    # Add competition tags and their parent continents
    elif category in TAG_COMPETITIONS:
        tags.append(category)
        if category in TAG_MAP:
            tags.extend(TAG_MAP[category])
    # Add direct continent tags
    elif category in TAG_CONTINENTS:
        tags.append(category)
    
    return list(set(tags))  # Remove duplicates


async def search_pexels_images(query, per_page=5):
    """Search Pexels for football images"""
    import urllib.request
    import urllib.parse
    import json
    import ssl
    
    url = "https://api.pexels.com/v1/search"
    headers = {"Authorization": PEXELS_API_KEY}
    
    params = {"query": query, "per_page": per_page, "orientation": "landscape"}
    
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        data = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=30, context=ctx) as response:
            result = json.loads(response.read())
            photos = result.get("photos", [])
            if photos:
                return photos[0].get("src", {}).get("large2x", photos[0].get("src", {}).get("large", ""))
    except Exception as e:
        print(f"    ⚠ Pexels error: {e}")
    return None


async def search_pixabay_images(query, per_page=5):
    """Search Pixabay for football images"""
    import urllib.request
    import urllib.parse
    import json
    import ssl
    
    url = "https://pixabay.com/api/"
    params = {"key": PIXABAY_API_KEY, "q": query, "per_page": per_page, "orientation": "horizontal"}
    
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        data = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=30, context=ctx) as response:
            result = json.loads(response.read())
            hits = result.get("hits", [])
            if hits:
                return hits[0].get("largeImageURL")
    except Exception as e:
        print(f"    ⚠ Pixabay error: {e}")
    return None


async def get_football_image():
    """Try multiple APIs to get a football image"""
    import random
    
    # Try each query with each API
    for _ in range(3):  # Try up to 3 times
        query = random.choice(FOOTBALL_QUERIES)
        
        # Try Pexels first
        url = await search_pexels_images(query)
        if url:
            print(f"    ✅ Got image from Pexels: {query}")
            return url
        
        # Try Pixabay
        url = await search_pixabay_images(query)
        if url:
            print(f"    ✅ Got image from Pixabay: {query}")
            return url
    
    return None

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

HERO_MARKERS = ("<!--KICKOFF_HERO_START-->", "<!--KICKOFF_HERO_END-->")
TRENDING_MARKERS = ("<!--KICKOFF_TRENDING_START-->", "<!--KICKOFF_TRENDING_END-->")
PICKS_MARKERS = ("<!--KICKOFF_PICKS_START-->", "<!--KICKOFF_PICKS_END-->")
LATEST_MARKERS = ("<!--KICKOFF_LATEST_START-->", "<!--KICKOFF_LATEST_END-->")


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


async def call_ollama(messages, model="llama3.2:1b", max_tokens=2000):
    """Use Ollama for local AI generation (free, private)"""
    import asyncio
    import json
    
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
    
    # Use subprocess instead of aiohttp to avoid async cancellation issues
    try:
        proc = await asyncio.create_subprocess_exec(
            "curl", "-s", "-X", "POST",
            "http://localhost:11434/api/generate",
            "-d", json.dumps(payload),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
        except asyncio.TimeoutError:
            proc.kill()
            print("  ⚠ Ollama timed out (180s)")
            return "[]"
        
        if proc.returncode != 0:
            print(f"  ⚠ Ollama curl failed (code {proc.returncode}): {stderr.decode()[:200]}")
            return "[]"
        
        data = json.loads(stdout.decode())
        response = data.get("response", "")
        print(f"    ✅ Ollama response: {response[:100]}...")
        return response
    except (Exception, asyncio.CancelledError) as e:
        print(f"  ⚠ Ollama error: {e}")
        return "[]"


async def call_openai(messages, api_key, response_format=None, max_tokens=2000, model="gpt-4o-mini"):
    # First try Ollama (local, free)
    try:
        result = await call_ollama(messages, model="llama3.2:1b", max_tokens=max_tokens)
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


def guess_category(headline):
    """Guess football category from headline text"""
    hl = headline.lower()
    if any(w in hl for w in ["transfer", "sign", "deal", "fee", "contract", "€", "£"]):
        return "Transfers"
    if any(w in hl for w in ["champions league", "ucl", "european cup"]):
        return "Champions League"
    if any(w in hl for w in ["premier league", "epl", "manchester", "liverpool", "arsenal", "chelsea", "tottenham", "newcastle"]):
        return "Premier League"
    if any(w in hl for w in ["la liga", "real madrid", "barcelona", "atletico", "el clasico"]):
        return "La Liga"
    if any(w in hl for w in ["serie a", "juventus", "milan", "inter", "napoli"]):
        return "Serie A"
    if any(w in hl for w in ["bundesliga", "bayern", "dortmund", "leipzig"]):
        return "Bundesliga"
    if any(w in hl for w in ["ligue 1", "psg", "monaco", "lyon", "marseille"]):
        return "Ligue 1"
    if any(w in hl for w in ["world cup", "qualifier"]):
        return "World Cup"
    if any(w in hl for w in ["copa america", "maracana"]):
        return "Copa America"
    if any(w in hl for w in ["europa league"]):
        return "Europa League"
    return "Premier League"

def guess_image_prompt(headline, category):
    """Generate a simple image prompt from headline"""
    hl = headline.lower()
    if "salah" in hl: return "Mohamed Salah celebrating a goal at Anfield under floodlights"
    if any(w in hl for w in ["transfer", "sign"]): return "Football player signing contract at stadium press conference"
    if any(w in hl for w in ["derby", "showdown"]): return "Two football teams facing off in a packed stadium"
    if "final" in hl: return "Football trophy in stadium with dramatic lighting"
    if any(w in hl for w in ["goal", "win", "victory"]): return "Football players celebrating a goal in stadium"
    if "manager" in hl or "coach" in hl: return "Football manager walking on pitch during match"
    if "injury" in hl: return "Football player being treated on pitch by medical staff"
    if any(w in hl for w in ["academy", "youth", "youngster"]): return "Young football player training on academy pitch"
    return f"Cinematic {category} football match under dramatic stadium lights"

async def generate_slider_content(api_key, rss_articles):
    """Build KICKOFF-style content directly from RSS articles"""
    print("  📰 Building content from real RSS articles...")
    
    if not rss_articles or len(rss_articles) < 4:
        print("    ⚠ Not enough RSS articles, using fallback")
        return get_fallback_slider()
    
    items = []
    for i, art in enumerate(rss_articles[:15]):
        title = art.get("title", f"Story {i+1}")[:60]
        description = art.get("description", "")
        category = guess_category(title)
        items.append({
            "headline": title,
            "description": description,
            "category": category,
            "content_type": "Match Reports",
            "category_tag": "LIVE" if i < 3 else "NEWS",
            "importance": 5 if i < 3 else (4 if i < 6 else 3),
            "image_prompt": guess_image_prompt(title, category),
            "source": art.get("source", "RSS"),
            "tags": get_tags_for_category(category, "Match Reports"),
        })
    
    print(f"    ✅ Built {len(items)} stories from RSS data")
    return items


def get_fallback_slider():
    return [
        {"headline": "Salah hat-trick sinks Manchester United at Anfield", "category": "Premier League",
         "category_tag": "LIVE", "image_prompt": "Mohamed Salah celebrating a hat-trick at Anfield under dramatic floodlights",
         "description": "Mohamed Salah scored a stunning hat-trick as Liverpool crushed Manchester United at Anfield in a Premier League classic. The Egyptian forward was in irresistible form, leaving United's defense in tatters."},
        {"headline": "Real Madrid agree €127M deal for Florian Wirtz", "category": "Transfer Talk",
         "category_tag": "BREAKING", "image_prompt": "Florian Wirtz signing contract at Santiago Bernabeu",
         "description": "Real Madrid have reached an agreement with Bayer Leverkusen for the transfer of Florian Wirtz in a deal worth €127 million. The German international is expected to sign a six-year contract."},
        {"headline": "Arsenal title hopes crushed by Newcastle smash-and-grab", "category": "Premier League",
         "category_tag": "LIVE", "image_prompt": "Newcastle players celebrating a last-minute winner at St James Park",
         "description": "Newcastle United delivered a crushing blow to Arsenal's Premier League title ambitions with a dramatic last-minute winner at St James' Park. The Gunners now trail league leaders by six points."},
        {"headline": "Barcelona on verge of financial collapse after La Liga rejection", "category": "La Liga",
         "category_tag": "EXCLUSIVE", "image_prompt": "Camp Nou stadium in darkness, moody atmosphere",
         "description": "Barcelona's financial crisis has deepened after La Liga rejected the club's latest economic viability plan. The Catalan giants face an uncertain future with potential sanctions looming."},
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
    
    # Try ImageRouter (has free models)
    print(f"    🎨 Trying ImageRouter...")
    result = await generate_imagerouter_image(prompt, size, filepath)
    if result:
        return result
    
    # Try DALL-E as fallback
    if api_key:
        print(f"    🎨 Trying DALL-E...")
        result = await generate_dalle_image(api_key, prompt, size, filepath)
        if result:
            return result
    
    return None


# ImageRouter API key (loaded from env or config.json)
IMAGEROUTER_API_KEY = os.environ.get("IMAGEROUTER_API_KEY", "")


async def generate_imagerouter_image(prompt, size, filepath):
    """Generate image using ImageRouter API (OpenAI-compatible)"""
    import aiohttp
    import json
    
    if not IMAGEROUTER_API_KEY:
        return None
    
    size_map = {
        "1792x1024": "1792x1024",
        "1024x1024": "1024x1024",
        "1024x768": "1024x768",
    }
    img_size = size_map.get(size, "1024x1024")
    
    full_prompt = f"{prompt}. Cinematic, photorealistic, professional sports photography, dramatic stadium lighting"
    
    headers = {
        "Authorization": f"Bearer {IMAGEROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    
    # Try free models in order of quality
    models = ["test/test", "flux/flux-schnell", "black-forest-labs/flux-schnell"]
    
    for model in models:
        body = {
            "prompt": full_prompt,
            "model": model,
            "size": img_size,
            "n": 1,
            "response_format": "b64_json",
        }
        
        try:
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(
                    "https://api.imagerouter.io/v1/openai/images/generations",
                    headers=headers, json=body,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    if resp.status != 200:
                        err = (await resp.text())[:100]
                        print(f"    ⚠ ImageRouter ({model}): {resp.status} {err}")
                        continue
                    data = await resp.json()
                    # OpenAI-compatible response format
                    if "data" in data and len(data["data"]) > 0:
                        img_data = data["data"][0]
                        b64 = img_data.get("b64_json", "")
                        if b64:
                            import base64
                            img_bytes = base64.b64decode(b64)
                            with open(filepath, "wb") as f:
                                f.write(img_bytes)
                            rel = os.path.relpath(filepath, PROJECT_DIR)
                            print(f"    ✅ Saved: {rel}")
                            return rel
                        url = img_data.get("url", "")
                        if url:
                            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as img_resp:
                                if img_resp.status == 200:
                                    with open(filepath, "wb") as f:
                                        f.write(await img_resp.read())
                                    rel = os.path.relpath(filepath, PROJECT_DIR)
                                    print(f"    ✅ Saved: {rel}")
                                    return rel
        except Exception as e:
            print(f"    ⚠ ImageRouter ({model}): {e}")
            continue
    
    return None





async def generate_gemini_image(gemini_key, prompt, size, filepath):
    """Generate image using Google Imagen via Gemini API"""
    import base64
    import random
    import ssl
    
    # Use Imagen 4 (latest image model)
    model = "imagen-4.0-generate-001"
    
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
        "instances": [{"prompt": full_prompt}],
        "parameters": {
            "sampleCount": 1,
            "aspectRatio": size.replace("x", "/"),
        }
    }
    
    try:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            async with session.post(
                f"https://us-central1-aiplatform.googleapis.com/v1/projects/PROJECT_ID/locations/us-central1/publishers/google/models/{model}:predict",
                headers={"Authorization": f"Bearer {gemini_key}", "Content-Type": "application/json"},
                json=body,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                if resp.status != 200:
                    err = await resp.text()
                    print(f"    ⚠ Gemini error {resp.status}: {err[:150]}")
                    return None
                data = await resp.json()
                if "predictions" in data and len(data["predictions"]) > 0:
                    img_b64 = data["predictions"][0].get("bytesBase64Encoded", "")
                    if img_b64:
                        img_bytes = base64.b64decode(img_b64)
                        with open(filepath, "wb") as f:
                            f.write(img_bytes)
                        rel = os.path.relpath(filepath, PROJECT_DIR)
                        print(f"    ✅ Saved: {rel}")
                        return rel
                print(f"    ⚠ Gemini response missing image")
                return None
    except Exception as e:
        print(f"    ❌ Gemini error: {e}")
    # Fallback: try Gemini 2.5 Flash for image output
    try:
        body = {
            "contents": [{"parts": [{"text": f"Generate a photorealistic image: {full_prompt}"}]}],
            "generationConfig": {"temperature": 1.0, "maxOutputTokens": 8192},
        }
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            async with session.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview:generateContent?key={gemini_key}",
                json=body,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if "candidates" in data and len(data["candidates"]) > 0:
                        parts = data["candidates"][0].get("content", {}).get("parts", [])
                        for part in parts:
                            if "inlineData" in part:
                                img_bytes = base64.b64decode(part["inlineData"]["data"])
                                with open(filepath, "wb") as f:
                                    f.write(img_bytes)
                                rel = os.path.relpath(filepath, PROJECT_DIR)
                                print(f"    ✅ Saved: {rel}")
                                return rel
    except Exception as e2:
        print(f"    ❌ Gemini fallback error: {e2}")
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
    # Slider (Top 4 - highest importance)
    {"headline": "Premier League title race reaches thrilling climax with 3 teams in contention", "category": "Premier League", "content_type": "Match Reports", "importance": 5, "image_prompt": "Premier League trophy at stadium", "category_tag": "BREAKING", "description": "The Premier League title race is set for a dramatic finale with three clubs separated by just two points at the top of the table. Every match now carries enormous weight as the season reaches its climax."},
    {"headline": "Real Madrid complete €120M signing of generational talent", "category": "Transfers", "content_type": "Transfers", "importance": 5, "image_prompt": "Player signing contract at Bernabeu", "category_tag": "BREAKING", "description": "Real Madrid have completed the signing of one of football's most exciting young talents in a deal worth €120 million. The player passed his medical and signed a five-year contract at the Bernabeu."},
    {"headline": "Champions League final: Tactical preview and key battles to watch", "category": "Champions League", "content_type": "Match Reports", "importance": 5, "image_prompt": "Champions League trophy in stadium", "category_tag": "BREAKING", "description": "With the Champions League final just days away, we break down the tactical battle ahead. From key duels to set-piece strategies, here is everything you need to know before kickoff."},
    {"headline": "Liverpool confirm new manager after Jurgen Klopp departure", "category": "Premier League", "content_type": "Transfers", "importance": 5, "image_prompt": "Anfield stadium at night", "category_tag": "BREAKING", "description": "Liverpool have officially announced their new manager following Jurgen Klopp's emotional departure from Anfield. The German tactician leaves behind a legacy that will be tough to match."},
    # Featured (4 posts)
    {"headline": "Barcelona's youth academy produces next generational superstar", "category": "La Liga", "content_type": "Interviews", "importance": 4, "image_prompt": "Young player training at La Masia", "category_tag": "FEATURED", "description": "Barcelona's famed La Masia academy has done it again, producing yet another generational talent who is already drawing comparisons to club legends. The 17-year-old has been turning heads in training."},
    {"headline": "Bayern Munich secure domestic double with dominant display", "category": "Bundesliga", "content_type": "Match Reports", "importance": 4, "image_prompt": "Bayern Munich celebration", "category_tag": "FEATURED", "description": "Bayern Munich have secured the domestic double after a commanding performance in the DFB-Pokal final. The Bavarian giants continue their stranglehold on German football."},
    {"headline": "PSG announce major squad overhaul for next season", "category": "Ligue 1", "content_type": "Transfers", "importance": 4, "image_prompt": "PSG stadium packed with fans", "category_tag": "FEATURED", "description": "Paris Saint-Germain have announced a comprehensive squad rebuild ahead of the new season, with several high-profile departures and arrivals expected at the Parc des Princes."},
    {"headline": "Inter Milan announce ambitious expansion plans for stadium", "category": "Serie A", "content_type": "Analysis", "importance": 4, "image_prompt": "San Siro stadium", "category_tag": "FEATURED", "description": "Inter Milan have unveiled ambitious plans to modernize and expand the iconic San Siro stadium. The project aims to increase capacity and enhance the fan experience."},
    # Other Stories (30+ posts)
    {"headline": "Rising star reveals childhood dream of playing for hometown club", "category": "Premier League", "content_type": "Interviews", "importance": 3, "image_prompt": "Player interview", "category_tag": "NEWS", "description": "In an exclusive interview, the talented youngster opened up about his childhood dream of playing for the club he grew up supporting. The emotional connection runs deep."},
    {"headline": "VAR controversy sparks debate among managers and fans", "category": "Premier League", "content_type": "Analysis", "importance": 3, "image_prompt": "VAR monitor", "category_tag": "NEWS", "description": "Another weekend of Premier League action has brought renewed debate over the use of VAR, with managers and fans divided on several key decisions that influenced match results."},
    {"headline": "Football legends gather for annual charity match event", "category": "Champions League", "content_type": "Opinion", "importance": 3, "image_prompt": "Charity football match", "category_tag": "NEWS", "description": "Some of football's greatest ever players came together for the annual charity match, raising millions for good causes while delighting fans with moments of magic."},
    {"headline": "Arsenal prepare for crucial north London derby", "category": "Premier League", "content_type": "Match Reports", "importance": 3, "image_prompt": "Arsenal stadium", "category_tag": "NEWS", "description": "Arsenal are intensifying their preparations for the upcoming north London derby against Tottenham. With both teams fighting for European places, the stakes could not be higher."},
    {"headline": "Chelsea youngster earns first senior international call-up", "category": "Premier League", "content_type": "News", "importance": 3, "image_prompt": "Chelsea celebration", "category_tag": "NEWS", "description": "A Chelsea academy graduate has received his first call-up to the senior national team, capping a remarkable breakthrough season at Stamford Bridge."},
    {"headline": "Manchester United confident of landing top transfer target", "category": "Transfers", "content_type": "Transfers", "importance": 3, "image_prompt": "Old Trafford", "category_tag": "NEWS", "description": "Manchester United officials are growing increasingly confident of securing their primary transfer target, with negotiations progressing positively behind the scenes."},
    {"headline": "Real Madrid and Barcelona set for El Clasico showdown", "category": "La Liga", "content_type": "Match Reports", "importance": 3, "image_prompt": "Camp Nou packed", "category_tag": "NEWS", "description": "The football world is counting down to the latest installment of El Clasico, with both Real Madrid and Barcelona desperate for victory in this pivotal La Liga encounter."},
    {"headline": "Juventus announce new signing from Serie A rivals", "category": "Serie A", "content_type": "Transfers", "importance": 3, "image_prompt": "Juventus stadium", "category_tag": "NEWS", "description": "Juventus have completed the signing of a highly-rated talent from a Serie A rival, strengthening their squad for the challenges ahead this season."},
    {"headline": "AC Milan target Champions League qualification", "category": "Serie A", "content_type": "Match Reports", "importance": 3, "image_prompt": "San Siro at night", "category_tag": "NEWS", "description": "AC Milan are focused on securing Champions League qualification as the Serie A season enters its decisive phase. Every point is crucial in the race for Europe."},
    {"headline": "Leipzig challenge Bayern for Bundesliga title", "category": "Bundesliga", "content_type": "Match Reports", "importance": 3, "image_prompt": "Red Bull Arena", "category_tag": "NEWS", "description": "RB Leipzig are emerging as genuine title challengers, keeping pace with Bayern Munich in the Bundesliga standings and refusing to let the defending champions pull away."},
    {"headline": "Dortmund youth prospect set for breakthrough season", "category": "Bundesliga", "content_type": "Interviews", "importance": 3, "image_prompt": "BVB fans", "category_tag": "NEWS", "description": "Borussia Dortmund's latest youth prospect is poised for a breakthrough campaign, with the club's famed development system producing yet another exciting talent."},
    {"headline": "Monaco youngster attracts Premier League attention", "category": "Ligue 1", "content_type": "Rumors", "importance": 3, "image_prompt": "Monaco match", "category_tag": "NEWS", "description": "Several Premier League clubs are monitoring the progress of Monaco's exciting young talent, with scouts regularly attending matches to track his development."},
    {"headline": "Lyon announce major investment in women's team", "category": "Ligue 1", "content_type": "News", "importance": 3, "image_prompt": "Lyon stadium", "category_tag": "NEWS", "description": "Olympique Lyonnais have announced a significant investment in their women's team, further cementing their status as one of the leading clubs in women's football."},
    {"headline": "South American stars set for Copa America battle", "category": "Copa America", "content_type": "Match Reports", "importance": 3, "image_prompt": "Maracanã stadium", "category_tag": "NEWS", "description": "South America's finest players are preparing to battle for continental supremacy as the Copa America tournament approaches. The competition promises drama and high-quality football."},
    {"headline": "Asian Champions League reaches knockout stages", "category": "Asia", "content_type": "Match Reports", "importance": 3, "image_prompt": "Asian football stadium", "category_tag": "NEWS", "description": "The Asian Champions League has reached the knockout stages, with teams from across the continent vying for a place in the quarter-finals."},
    {"headline": "MLS expansion team announces stadium plans", "category": "North America", "content_type": "News", "importance": 3, "image_prompt": "MLS stadium", "category_tag": "NEWS", "description": "Major League Soccer's newest expansion team has unveiled ambitious plans for a state-of-the-art stadium, signaling the league continued growth across North America."},
    {"headline": "Tottenham Hotspur face crucial run of fixtures", "category": "Premier League", "content_type": "Match Reports", "importance": 2, "image_prompt": "Tottenham stadium", "category_tag": "NEWS", "description": "Tottenham Hotspur face a defining run of fixtures that could shape their entire season. Manager Ange Postecoglou will be looking for strong performances."},
    {"headline": "Newcastle United target top four finish", "category": "Premier League", "content_type": "Analysis", "importance": 2, "image_prompt": "St James Park", "category_tag": "NEWS", "description": "Newcastle United are setting their sights on a top-four Premier League finish as the club continues its remarkable transformation under the current ownership."},
    {"headline": "Atletico Madrid prepare for derby against Real Madrid", "category": "La Liga", "content_type": "Match Reports", "importance": 2, "image_prompt": "Wanda Metropolitano", "category_tag": "NEWS", "description": "Atletico Madrid are fine-tuning their preparations for the highly anticipated Madrid derby against rivals Real Madrid at the Wanda Metropolitano."},
    {"headline": "Sevilla continue impressive European campaign", "category": "La Liga", "content_type": "Match Reports", "importance": 2, "image_prompt": "Sevilla celebration", "category_tag": "NEWS", "description": "Sevilla are continuing their impressive run in European competition, with the Spanish side once again proving to be a formidable opponent on the continental stage."},
    {"headline": "Napoli boss discusses title chances this season", "category": "Serie A", "content_type": "Interviews", "importance": 2, "image_prompt": "Napoli stadium", "category_tag": "NEWS", "description": "Napoli's manager has spoken confidently about the club's title chances this season, believing the squad has what it takes to challenge for the Scudetto."},
    {"headline": "Lazio eye European qualification spots", "category": "Serie A", "content_type": "Match Reports", "importance": 2, "image_prompt": "Stadio Olimpico", "category_tag": "NEWS", "description": "Lazio are setting their sights on European qualification as the Serie A season progresses, with the Roman club aiming for a return to continental competition."},
    {"headline": "Bundesliga title race heats up with Bayern leading", "category": "Bundesliga", "content_type": "Match Reports", "importance": 2, "image_prompt": "Allianz Arena", "category_tag": "NEWS", "description": "The Bundesliga title race is heating up with Bayern Munich leading the pack, but several challengers are lurking close behind ready to pounce on any slip."},
    {"headline": "Leverkusen challenge traditional Bundesliga powerhouses", "category": "Bundesliga", "content_type": "Analysis", "importance": 2, "image_prompt": "BayArena", "category_tag": "NEWS", "description": "Bayer Leverkusen are emerging as genuine challengers to the traditional Bundesliga powerhouses, with an exciting brand of football winning plaudits across Germany."},
    {"headline": "Marseille aim for strong finish to season", "category": "Ligue 1", "content_type": "Match Reports", "importance": 2, "image_prompt": "Velodrome stadium", "category_tag": "NEWS", "description": "Olympique de Marseille are determined to finish the season strongly, with the club aiming to secure a Champions League berth for next campaign."},
    {"headline": "Nice announce ambitious five-year plan", "category": "Ligue 1", "content_type": "Analysis", "importance": 2, "image_prompt": "Allianz Riviera", "category_tag": "NEWS", "description": "OGC Nice have unveiled an ambitious five-year strategic plan aimed at establishing the club among the elite of French and European football."},
    {"headline": "Europa League draw throws up intriguing ties", "category": "Europa League", "content_type": "News", "importance": 2, "image_prompt": "UEFA trophy", "category_tag": "NEWS", "description": "The Europa League draw has produced some fascinating matchups, with several heavyweight clubs facing tricky tests in the knockout stages."},
    {"headline": "FA Cup quarter-finals set to deliver drama", "category": "FA Cup", "content_type": "Match Reports", "importance": 2, "image_prompt": "Wembley stadium", "category_tag": "NEWS", "description": "The FA Cup quarter-finals promise plenty of drama as the remaining clubs battle for a place at Wembley and a shot at football's oldest domestic trophy."},
    {"headline": "World Cup qualifiers resume across continents", "category": "World Cup", "content_type": "Match Reports", "importance": 2, "image_prompt": "World Cup stadium", "category_tag": "NEWS", "description": "World Cup qualifying campaigns resume across the globe as nations continue their journeys toward securing a place at football's greatest tournament."},
    {"headline": "European Championship qualifier results round-up", "category": "European Championship", "content_type": "Match Reports", "importance": 2, "image_prompt": "Euro trophy", "category_tag": "NEWS", "description": "A round-up of all the action from the latest European Championship qualifiers, with several teams taking significant steps toward booking their place at the finals."},
    {"headline": "Transfer rumors intensify as window approaches", "category": "Transfers", "content_type": "Rumors", "importance": 2, "image_prompt": "Transfer news", "category_tag": "NEWS", "description": "Transfer rumors are intensifying across Europe as the summer window approaches, with clubs lining up potential deals and agents working behind the scenes."},
]

FALLBACK_IMAGES = [
    # Premier League / Stadium images
    "https://images.unsplash.com/photo-1511882150382-421056c89033?w=1024&h=768&fit=crop",
    "https://images.unsplash.com/photo-1574629810360-7efbbe195018?w=1024&h=768&fit=crop",
    # Football action
    "https://images.unsplash.com/photo-1431324155629-1a6deb1dec8d?w=1024&h=768&fit=crop",
    "https://images.unsplash.com/photo-1579952363873-27f3bade9f55?w=1024&h=768&fit=crop",
    # Players / Goals
    "https://images.unsplash.com/photo-1489944440615-453fc2b6a9a9?w=1024&h=768&fit=crop",
    "https://images.unsplash.com/photo-1560272564-c8304700f87c?w=1024&h=768&fit=crop",
    # Stadium / Crowd
    "https://images.unsplash.com/photo-1507501336603-6e31db2be093?w=1024&h=768&fit=crop",
    "https://images.unsplash.com/photo-1575361204480-aadea25e6e68?w=1024&h=768&fit=crop",
    # Celebration
    "https://images.unsplash.com/photo-1606925797300-0b35e9d1794e?w=1024&h=768&fit=crop",
    "https://images.unsplash.com/photo-1540747913346-19e32dc3e97e?w=1024&h=768&fit=crop",
    # Additional diverse images
    "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?w=1024&h=768&fit=crop",
    "https://images.unsplash.com/photo-1522778119026-d647f0565c6a?w=1024&h=768&fit=crop",
    "https://images.unsplash.com/photo-1459865264687-595d652de67e?w=1024&h=768&fit=crop",
    "https://images.unsplash.com/photo-1530046339160-ce3e530c7d2f?w=1024&h=768&fit=crop",
    "https://images.unsplash.com/photo-1503614472-8c93d56e92ce?w=1024&h=768&fit=crop",
]


def get_post_id(item, index):
    """Generate unique post ID in DDMMYY-0001 format"""
    now = datetime.now()
    date_str = now.strftime("%d%m%y")
    return f"{date_str}-{index:04d}"


def format_headline_title(headline):
    """Format headline to Title Case, fix apostrophe-s, remove semicolons"""
    import re
    headline = headline.replace(";", " - ")
    
    # Use regex to properly title case without capitalizing after apostrophes
    # First apply title case, then fix the 's pattern
    headline = headline.title()
    
    # Fix Gerrard's -> Gerrard's (lowercase s after apostrophe)
    headline = re.sub(r"'S\b", "'s", headline)
    headline = re.sub(r"'T\b", "'t", headline)
    headline = re.sub(r"'M\b", "'m", headline)
    headline = re.sub(r"'D\b", "'d", headline)
    headline = re.sub(r"'L\b", "'l", headline)
    headline = re.sub(r"'V\b", "'v", headline)
    headline = re.sub(r"'R\b", "'r", headline)
    
    # Clean up multiple spaces
    headline = ' '.join(headline.split())
    return headline


def build_hero_js(items, images):
    """Generate heroSlides JS array"""
    lines = []
    for i, item in enumerate(items):
        img = images.get(item.get("_key", ""), FALLBACK_IMAGES[i % len(FALLBACK_IMAGES)])
        tag = item.get("category_tag", "Breaking")
        title = format_headline_title(item.get("headline", "Football News").replace("**", "")).replace('"', '\\"')
        excerpt = item.get("excerpt", title).replace('"', '\\"')
        post_id = item.get("_post_id", get_post_id(item, i))
        date = datetime.now().strftime("%Y-%m-%d")
        lines.append(f'''            {{ tag: "{tag}", title: "{title}", excerpt: "{excerpt}", image: "{img}", link: "posts/{post_id}.html", date: "{date}" }},''')
    return "\n".join(lines)


def build_trending_html(items, images):
    """Generate trending mini-cards"""
    html = ""
    times = ["15 min ago", "28 min ago", "42 min ago"]
    leagues_map = {
        "Premier League": "premier", "La Liga": "laliga", "Serie A": "seriea",
        "Bundesliga": "bundesliga", "Ligue 1": "ligue1",
    }
    for i, item in enumerate(items):
        cat = item.get("category", "Premier League")
        league = leagues_map.get(cat, "premier")
        headline = format_headline_title(item.get("headline", "Football News").replace("**", ""))
        time_str = times[i] if i < len(times) else f"{i+1} hour ago"
        post_id = item.get("_post_id", get_post_id(item, i + 10))
        html += f"""                    <a href="posts/{post_id}.html" class="mini-card">
                        <span class="num">{i + 1}</span>
                        <div class="mini-body">
                            <div class="mini-tag" data-league="{league}">{cat}</div>
                            <h3 class="mini-title">{headline}</h3>
                            <div class="mini-meta">{time_str}</div>
                        </div>
                    </a>
"""
    return html


def build_picks_html(items, images):
    """Generate editor's picks mag-cards"""
    html = ""
    sizes = ["w=600&h=500&fit=crop", "w=300&h=300&fit=crop", "w=300&h=300&fit=crop", "w=600&h=250&fit=crop"]
    leagues_map = {
        "Premier League": "premier", "La Liga": "laliga", "Serie A": "seriea",
        "Bundesliga": "bundesliga", "Ligue 1": "ligue1",
    }
    for i, item in enumerate(items):
        cat = item.get("category", "Premier League")
        league = leagues_map.get(cat, "premier")
        img = images.get(item.get("_key", ""), FALLBACK_IMAGES[(i + 5) % len(FALLBACK_IMAGES)] + "&" + sizes[i % len(sizes)])
        headline = format_headline_title(item.get("headline", "Football News").replace("**", ""))
        post_id = item.get("_post_id", get_post_id(item, i + 20))
        html += f"""                <a href="posts/{post_id}.html" class="mag-card">
                    <img src="{img}" alt="">
                    <div class="overlay"></div>
                    <div class="mag-text">
                        <span class="mag-tag" data-league="{league}">{cat}</span>
                        <h3 class="mag-title">{headline}</h3>
                    </div>
                </a>
"""
    return html


def build_latest_html(items):
    """Generate latest story-tiles"""
    html = ""
    for i, item in enumerate(items):
        headline = format_headline_title(item.get("headline", "Football News").replace("**", ""))
        post_id = item.get("_post_id", get_post_id(item, i + 30))
        html += f"""                <a href="posts/{post_id}.html" class="story-tile">
                    <h3 class="story-tile-title">{headline}</h3>
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
    headline = format_headline_title(item.get("headline", "Football News").replace("**", ""))
    category = item.get("category", "Premier League")
    tag = item.get("category_tag", "LIVE")
    time_str = "Just now"
    
    # Fix image path for post pages (they're in posts/ subdirectory)
    img = image_url if image_url else FALLBACK_IMAGES[0]
    if img and not img.startswith("http") and not img.startswith("../"):
        img = f"../{img}"
    
    html = html.replace("POST_HEADLINE", headline)
    html = html.replace("POST_CATEGORY", category)
    html = html.replace("POST_TAG", tag)
    html = html.replace("POST_TIME", time_str)
    html = html.replace("POST_CONTENT", content)
    html = html.replace("POST_HERO_IMAGE", img)
    
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
    
    # Generate stories with importance scores (1-5)
    all_stories = await generate_slider_content(api_key, rss_headlines)
    
    # Sort by importance (highest first)
    all_stories.sort(key=lambda x: x.get("importance", 3), reverse=True)
    
    # Pad to at least 25 items for full layout
    if len(all_stories) < 25:
        print(f"  ⚠ Only {len(all_stories)} stories, padding with fallback content")
        existing_categories = {s.get("category") for s in all_stories}
        fallback_items = [f for f in FALLBACK_CONTENT if f.get("category") not in existing_categories]
        all_stories.extend(fallback_items[:40 - len(all_stories)])
    
    # Assign to sections based on importance
    # Site layout: 5 hero + 3 trending + 4 picks + 12 latest (4x3) = 24 total
    hero_items = all_stories[:5]
    trending_items = all_stories[5:8]
    picks_items = all_stories[8:12]
    latest_items = all_stories[12:24]
    
    # Ensure minimum counts
    trending_items = trending_items[:3]
    picks_items = picks_items[:4]
    latest_items = latest_items[:12]
    
    # Add section-specific tags
    for item in hero_items:
        item["category_tag"] = "Breaking" if item.get("importance", 3) >= 5 else "LIVE"
        item["excerpt"] = item.get("description", item.get("headline", ""))[:150]
    for item in trending_items:
        item["category_tag"] = "TRENDING"
    for item in picks_items:
        item["category_tag"] = "PICK"
    for item in latest_items:
        item["category_tag"] = "NEWS"
    
    print(f"    📊 Priority assignment:")
    print(f"       🔴 Hero ({len(hero_items)}): {[s.get('importance', 3) for s in hero_items]}")
    print(f"       🟠 Trending ({len(trending_items)}): {[s.get('importance', 3) for s in trending_items]}")
    print(f"       🟡 Picks ({len(picks_items)}): {[s.get('importance', 3) for s in picks_items]}")
    print(f"       🟢 Latest ({len(latest_items)}): {[s.get('importance', 3) for s in latest_items]}")
    
    # Generate images for each story
    
    # Check for API keys
    recraft_key = os.environ.get("RECRAFT_API_KEY", "")
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    global IMAGEROUTER_API_KEY
    
    if not recraft_key:
        config_file = PROJECT_DIR / "config.json"
        if config_file.exists():
            with open(config_file) as f:
                cfg = json.load(f)
                recraft_key = cfg.get("api_keys", {}).get("recraft", "")
                if not gemini_key:
                    gemini_key = cfg.get("api_keys", {}).get("gemini", "")
                if not IMAGEROUTER_API_KEY:
                    IMAGEROUTER_API_KEY = cfg.get("api_keys", {}).get("imagerouter", "")
    
    # Show key status
    print(f"\n🔑 API Keys status:")
    print(f"   OpenAI (DALL-E): {'✓' if api_key and api_key != 'your-openai-api-key-here' else '✗'}")
    print(f"   ImageRouter: {'✓' if IMAGEROUTER_API_KEY else '✗'}")
    print(f"   Gemini: {'✓' if gemini_key else '✗'}")
    
    # Note: Puter is tried first (free), then Gemini, then DALL-E
    if recraft_key:
        print("  → Recraft available as backup")
    if gemini_key:
        print("  → Gemini available as backup")
    if api_key:
        print("  → DALL-E available as backup")
    
    # Add _key and _post_id to each section for post IDs
    all_items = []
    for i, item in enumerate(hero_items):
        item["_key"] = f"hero_{i}"
        item["_post_id"] = get_post_id(item, i)
        all_items.append(item)
    for i, item in enumerate(trending_items):
        item["_key"] = f"trending_{i}"
        item["_post_id"] = get_post_id(item, i + 10)
        all_items.append(item)
    for i, item in enumerate(picks_items):
        item["_key"] = f"picks_{i}"
        item["_post_id"] = get_post_id(item, i + 20)
        all_items.append(item)
    for i, item in enumerate(latest_items):
        item["_key"] = f"latest_{i}"
        item["_post_id"] = get_post_id(item, i + 30)
        all_items.append(item)

    print(f"\n🎨 Generating images for hero + picks ({5 + 4} images)...")
    image_map = {}

    for i, item in enumerate(all_items):
        if item["_key"].startswith("hero_") or item["_key"].startswith("picks_"):
            key = item["_key"]
            size = "1792x1024" if key.startswith("hero_") else "1024x1024"
            filename = f"{key}.png"
            filepath = IMAGES_DIR / filename
            
            # Skip if image already exists
            if filepath.exists():
                print(f"    ⏭️ Skipping {key} (already exists)")
                image_map[key] = f"images/{filename}"
                continue
            
            rel = await generate_image(api_key, item["image_prompt"], size, filepath, recraft_key, gemini_key)
            if rel:
                image_map[key] = rel
            else:
                football_img = await get_football_image()
                if football_img:
                    image_map[key] = football_img
                else:
                    image_map[key] = FALLBACK_IMAGES[i % len(FALLBACK_IMAGES)]

    # 4. Update HTML
    print("\n🌐 Updating website...")
    with open(HTML_FILE, "r") as f:
        html = f.read()

    hero_js = build_hero_js(hero_items, image_map)
    html = replace_between(html, HERO_MARKERS, hero_js)
    
    trending_html = build_trending_html(trending_items, image_map)
    html = replace_between(html, TRENDING_MARKERS, trending_html)
    
    picks_html = build_picks_html(picks_items, image_map)
    html = replace_between(html, PICKS_MARKERS, picks_html)
    
    latest_html = build_latest_html(latest_items)
    html = replace_between(html, LATEST_MARKERS, latest_html)

    with open(HTML_FILE, "w") as f:
        f.write(html)

    print("✅ Website updated!")

    # 4b. Generate individual post pages (if enabled)
    if GENERATE_POST_PAGES:
        print("📝 Generating post pages...")
        for i, item in enumerate(all_items):
            post_id = item.get("_post_id", get_post_id(item, i))
            image_key = item.get("_key", "")
            image_url = image_map.get(image_key, FALLBACK_IMAGES[0])
            
            # Generate article content
            headline = format_headline_title(item.get("headline", "Football News").replace("**", ""))
            category = item.get("category", "Premier League")
            description = item.get("description", "")
            
            if description and len(description) > 30:
                content = f"""
            <p>{headline}</p>
            <p>{description}</p>
            <p>KICKOFF will continue to follow this story as it develops. Check back for the latest updates and expert analysis.</p>
            """
            else:
                # Generate unique content based on headline hash
                import hashlib
                seed = hashlib.md5(headline.encode()).digest()[0] % 3
                templates = [
                    f"""<p>In what is shaping up to be a significant development in {category}, the football world is reacting to the latest news surrounding {headline.lower()}.</p><p>Sources close to the situation indicate that this story could have major implications for the remainder of the season, with fans and pundits alike weighing in on what this means for the clubs involved.</p><p>KICKOFF will bring you all the latest updates as this story develops. Stay tuned for expert analysis and breaking coverage.</p>""",
                    f"""<p>{headline} — a story that has captured the attention of football fans worldwide. The developments coming out of {category} suggest this could be a defining moment in the season.</p><p>Those close to the negotiations confirm that discussions have been ongoing, with both parties working toward a resolution that could reshape the landscape of the sport.</p><p>Bookmark this page for the latest information. KICKOFF is committed to bringing you comprehensive coverage of this developing story.</p>""",
                    f"""<p>The football community is buzzing with the news of {headline.lower()}. This {category} story has all the makings of a classic, with drama and intrigue at every turn.</p><p>Behind-the-scenes sources reveal that the situation is fluid, with multiple factors at play. The coming days will be crucial in determining how this story unfolds.</p><p>Keep checking KICKOFF for the most up-to-date information and insights from our team of football experts.</p>""",
                ]
                content = templates[seed]
            
            post_html = generate_post_html(item, image_url, content)
            if post_html:
                post_file = PROJECT_DIR / "posts" / f"{post_id}.html"
                os.makedirs(PROJECT_DIR / "posts", exist_ok=True)
                with open(post_file, "w") as f:
                    f.write(post_html)
        
        print(f"   ✅ Generated {len(all_items)} post pages")
    else:
        print("   ⏭️ Skipping post page generation")

    # 5. Save content data
    content_data = {
        "generated_at": datetime.now().isoformat(),
        "rss_headlines_used": len(rss_headlines),
        "sections": {
            "hero": hero_items,
            "trending": trending_items,
            "picks": picks_items,
            "latest": latest_items,
        },
    }
    with open(PROJECT_DIR / "content_data.json", "w") as f:
        json.dump(content_data, f, indent=2)

    print("\n📤 Pushing to GitHub...")
    import subprocess
    try:
        subprocess.run(["git", "add", "-A"], cwd=PROJECT_DIR, check=True)
        subprocess.run(["git", "commit", "-m", f"Auto-update: {datetime.now().strftime('%Y-%m-%d %H:%M')}"], cwd=PROJECT_DIR, check=True)
        if AUTO_PUSH:
            subprocess.run(["git", "push", "origin", "main:gh-pages"], cwd=PROJECT_DIR, check=True)
            print("   ✅ Pushed to GitHub")
        else:
            print("   ⏭️ Skipping push (AUTO_PUSH=False)")
    except Exception as e:
        if "nothing to commit" in str(e):
            print("   ℹ️ No changes to commit")
        else:
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
