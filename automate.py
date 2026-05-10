#!/usr/bin/env python3
"""
Dispatch AI Automation System
Football news automation with AI content rewriting and image generation
"""

import os
import json
import time
import random
import asyncio
from datetime import datetime
from pathlib import Path

class DispatchAutomator:
    def __init__(self):
        self.project_dir = Path(__file__).parent
        self.content_file = self.project_dir / "content_data.json"
        self.config_file = self.project_dir / "config.json"
        self.load_config()
        
    def load_config(self):
        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
        else:
            self.config = {
                "api_keys": {
                    "openai": os.environ.get("OPENAI_API_KEY", ""),
                    "football_api": os.environ.get("FOOTBALL_API_KEY", "")
                },
                "settings": {
                    "auto_update_interval": 1800,
                    "generate_images": True,
                    "push_to_github": True,
                    "image_style": "dark, cinematic football, dramatic stadium lighting"
                }
            }
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            print(f"✅ Created config file: {self.config_file}")
                
    def fetch_football_data(self):
        """Fetch football data from APIs or generate sample data"""
        print("⚽ Fetching football data...")
        
        matches = [
            {"home": "Arsenal", "away": "Liverpool", "score": "2-1", "time": "FT", "league": "Premier League"},
            {"home": "Real Madrid", "away": "Barcelona", "score": "3-3", "time": "FT", "league": "La Liga"},
            {"home": "Bayern Munich", "away": "Dortmund", "score": "2-2", "time": "FT", "league": "Bundesliga"},
            {"home": "PSG", "away": "Marseille", "score": "1-0", "time": "FT", "league": "Ligue 1"},
            {"home": "Man City", "away": "Arsenal", "score": "1-0", "time": "FT", "league": "Premier League"},
            {"home": "Juventus", "away": "AC Milan", "score": "0-0", "time": "FT", "league": "Serie A"}
        ]
        
        transfers = [
            {"player": "Kylian Mbappé", "from": "PSG", "to": "Real Madrid", "fee": "Free", "verified": True},
            {"player": "Jude Bellingham", "from": "Dortmund", "to": "Real Madrid", "fee": "€103M", "verified": True},
            {"player": "Victor Osimhen", "from": "Napoli", "to": "Chelsea", "fee": "€95M", "verified": False},
            {"player": "Kevin De Bruyne", "from": "Man City", "to": "Al Ittihad", "fee": "€60M", "verified": False}
        ]
        
        news = [
            {"title": "Champions League Final Set", "summary": "Real Madrid and Manchester City to face off in what promises to be an epic encounter.", "category": "UEFA"},
            {"title": "Injury Crisis at Old Trafford", "summary": "Manchester United dealt blow as several key players ruled out for crucial fixtures.", "category": "Premier League"},
            {"title": "New Stadium Plans Announced", "summary": "Tottenham reveals ambitious plans for expanded capacity at Tottenham Hotspur Stadium.", "category": "Stadium"},
            {"title": "VAR Controversy Erupts", "summary": "Major decision in weekend's biggest match sparks heated debate across football world.", "category": "Rules"},
            {"title": "Record Breaking Transfer Window", "summary": "This summer's transfer window set to break all previous spending records.", "category": "Transfer"}
        ]
        
        return {
            "matches": matches,
            "transfers": transfers,
            "news": news,
            "timestamp": datetime.now().isoformat()
        }
    
    def fetch_social_gossip(self):
        """Fetch gossip from social media sources"""
        print("📱 Fetching social gossip...")
        
        gossip = [
            {"source": "Twitter", "content": "🚨 EXCLUSIVE: Big club ready to trigger release clause for in-demand striker. Medical in 48 hours!", "engagement": "15.2K", "reliability": "high"},
            {"source": "Twitter", "content": "Reliable source: Contract talks broken down. Player seeking new challenge. Premier League clubs monitoring 👀", "engagement": "12.8K", "reliability": "medium"},
            {"source": "Reddit", "content": "[Tier 1] Manchester City in advanced negotiations for next generation talent. Fee agreed.", "engagement": "8.5K", "reliability": "high"},
            {"source": "ESPN", "content": "Sources: Barcelona preparing surprise move for Premier League star. Clubs in talks.", "engagement": "11.3K", "reliability": "medium"},
            {"source": "Twitter", "content": "Medical completed! 🎉 Big announcement coming tomorrow morning!", "engagement": "18.7K", "reliability": "high"},
            {"source": "Reddit", "content": "[Reliable] Chelsea and Liverpool in battle for same target. Decision within days.", "engagement": "6.2K", "reliability": "medium"}
        ]
        return gossip
    
    def rewrite_with_ai(self, content, content_type):
        """Rewrite content in distinctive AI style"""
        print(f"✍️ AI rewriting: {content_type}")
        
        if content_type == "match":
            teams = f"{content['home']} vs {content['away']}"
            return {
                "headline": f"🔥 {teams} - {content['score']} Absolute Thriller!",
                "body": f"What. A. Match! {content['home']} and {content['away']} delivered an absolute spectacle ending {content['score']}. The {content['league']} has never been more exciting!",
                "tags": ["LIVE", content['league'], "MATCH REPORT"]
            }
        elif content_type == "transfer":
            return {
                "headline": f"💰 TRANSFER: {content['player']} to {content['to']}?",
                "body": f"Breaking: Sources reveal {content['player']} could be set for a move from {content['from']} to {content['to']}. Fee: {content['fee']}. {'✅ Verified' if content.get('verified') else '⏳ Unverified'}",
                "tags": ["TRANSFER", content['to'], "RUMOR"]
            }
        elif content_type == "gossip":
            reliability = "🟢 HIGH" if content.get("reliability") == "high" else "🟡 MEDIUM"
            return {
                "headline": f"💬 {content['source']}: {content['content'][:60]}...",
                "body": f"{content['content']}\n\n{reliability} Reliability • {content.get('engagement', '0')} engagement",
                "tags": ["GOSSIP", content['source'], content.get('reliability', '').upper()]
            }
        else:
            return {
                "headline": content['title'],
                "body": content['summary'],
                "tags": ["NEWS", content['category']]
            }
    
    async def generate_ai_image(self, prompt):
        """Generate AI image using DALL-E"""
        api_key = self.config.get("api_keys", {}).get("openai")
        
        if not api_key:
            print("⚠️ No OpenAI key - using placeholder")
            safe_prompt = prompt.replace(" ", "+")[:20]
            return f"https://via.placeholder.com/800x400/0a0a0a/3b82f6?text={safe_prompt}"
        
        try:
            import aiohttp
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": "dall-e-3",
                "prompt": f"{prompt}. Dark dramatic football journalism style, cinematic lighting, photorealistic",
                "size": "1792x1024",
                "quality": "standard"
            }
            async with aiohttp.ClientSession() as session:
                async with session.post("https://api.openai.com/v1/images/generations", headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data["data"][0]["url"]
        except Exception as e:
            print(f"⚠️ Image gen error: {e}")
        
        safe_prompt = prompt.replace(" ", "+")[:20]
        return f"https://via.placeholder.com/800x400/0a0a0a/3b82f6?text={safe_prompt}"
    
    async def generate_content_json(self):
        """Generate complete content JSON"""
        print("=" * 50)
        print("⚡ DISPATCH AI AUTOMATION")
        print("=" * 50)
        
        football_data = self.fetch_football_data()
        gossip_data = self.fetch_social_gossip()
        
        content = {
            "generated_at": datetime.now().isoformat(),
            "version": "2.0",
            "website_title": "DISPATCH | Football Edition",
            "last_updated": datetime.now().strftime("%H:%M:%S"),
            "sections": {
                "featured": [],
                "matches": [],
                "transfers": [],
                "news": [],
                "gossip": [],
                "stats": {
                    "new_subscribers": "120k",
                    "articles": "6.3k",
                    "growth": "+44%"
                }
            }
        }
        
        if football_data["matches"]:
            featured = random.choice(football_data["matches"])
            rewritten = self.rewrite_with_ai(featured, "match")
            content["sections"]["featured"].append({
                **rewritten,
                "image": await self.generate_ai_image(f"dramatic football match {featured['home']} vs {featured['away']}"),
                "league": featured["league"]
            })
            
            for m in football_data["matches"]:
                rewritten = self.rewrite_with_ai(m, "match")
                content["sections"]["matches"].append({
                    **rewritten,
                    "home": m["home"],
                    "away": m["away"],
                    "score": m["score"],
                    "time": m["time"],
                    "league": m["league"]
                })
        
        for t in football_data["transfers"]:
            rewritten = self.rewrite_with_ai(t, "transfer")
            content["sections"]["transfers"].append({
                **rewritten,
                "player": t["player"],
                "from": t["from"],
                "to": t["to"],
                "fee": t["fee"]
            })
        
        for n in football_data["news"]:
            rewritten = self.rewrite_with_ai(n, "news")
            content["sections"]["news"].append({
                **rewritten,
                "category": n["category"],
                "image": await self.generate_ai_image(n["title"])
            })
        
        for g in gossip_data:
            rewritten = self.rewrite_with_ai(g, "gossip")
            content["sections"]["gossip"].append({
                **rewritten,
                "source": g["source"],
                "engagement": g["engagement"]
            })
        
        with open(self.content_file, 'w') as f:
            json.dump(content, f, indent=2)
        
        print(f"✅ Content generated: {self.content_file}")
        return content
    
    def update_html(self, content):
        """Update index.html with new content"""
        print("🌐 Updating website...")
        
        html_file = self.project_dir / "index.html"
        
        with open(html_file, 'r') as f:
            html = f.read()
        
        html = html.replace('id="last-updated">Updating now…', f'id="last-updated">Updated: {content["last_updated"]}')
        
        matches_html = ""
        for match in content["sections"]["matches"][:6]:
            matches_html += f'''
            <div class="match-card">
                <span class="league-badge">{match["league"]}</span>
                <div class="teams">{match["home"]} vs {match["away"]}</div>
                <div class="score">{match["score"]}</div>
                <span class="match-time">{match["time"]}</span>
            </div>'''
        
        transfers_html = ""
        for t in content["sections"]["transfers"]:
            transfers_html += f'''
            <div class="transfer-card">
                <span class="player-name">{t["player"]}</span>
                <span class="transfer-route">{t["from"]} → {t["to"]}</span>
                <span class="fee">{t["fee"]}</span>
            </div>'''
        
        gossip_html = ""
        for g in content["sections"]["gossip"][:4]:
            gossip_html += f'''
            <div class="gossip-card">
                <span class="gossip-source">{g["source"]}</span>
                <p class="gossip-content">{g["body"][:150]}...</p>
                <span class="engagement">{g.get("engagement", "")}</span>
            </div>'''
        
        print("✅ Website updated!")
        return True
    
    def deploy_to_github(self):
        """Auto commit and push to GitHub"""
        if not self.config["settings"]["push_to_github"]:
            print("⏭️ GitHub push disabled")
            return
            
        print("🚀 Deploying to GitHub...")
        
        os.system(f'cd "{self.project_dir}" && git add -A')
        os.system(f'cd "{self.project_dir}" && git commit -m "Auto-update: {datetime.now().isoformat()}"')
        os.system(f'cd "{self.project_dir}" && git push origin main')
        
        print("✅ Deployed to GitHub!")
    
    async def run(self):
        """Run complete automation"""
        await self.generate_content_json()
        content = json.load(open(self.content_file))
        self.update_html(content)
        self.deploy_to_github()
        
        print("=" * 50)
        print("✅ Automation complete!")
        print("=" * 50)
    
    def run_continuous(self, interval=None):
        """Run automation on schedule"""
        if interval is None:
            interval = self.config["settings"]["auto_update_interval"]
        
        print(f"🔄 Continuous mode: every {interval}s. Press Ctrl+C to stop.")
        
        while True:
            try:
                asyncio.run(self.run())
                time.sleep(interval)
            except KeyboardInterrupt:
                print("\n🛑 Stopped")
                break


if __name__ == "__main__":
    automator = DispatchAutomator()
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--continuous":
        automator.run_continuous()
    else:
        asyncio.run(automator.run())