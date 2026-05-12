#!/usr/bin/env python3
"""
KICKOFF AI Image Generator
Generates cinematic football images and embeds them into the website
"""

import os
import json
import asyncio
import aiohttp
from pathlib import Path

class KICKOFFImageGenerator:
    def __init__(self):
        self.project_dir = Path(__file__).parent
        self.html_file = self.project_dir / "index.html"
        self.api_key = os.environ.get("OPENAI_API_KEY", "")
        
    def load_html(self):
        with open(self.html_file, 'r') as f:
            return f.read()
    
    def save_html(self, html):
        with open(self.html_file, 'w') as f:
            f.write(html)
    
    async def generate_image(self, prompt, size="1024x1024"):
        """Generate image using DALL-E 3"""
        if not self.api_key:
            print("⚠️ No OpenAI API key - using fallback image")
            return self.get_fallback_image(prompt)
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        full_prompt = f"{prompt}. Cinematic dark moody aesthetic, dramatic stadium lighting, film print grain, high contrast, professional sports photography, photorealistic"
        
        payload = {
            "model": "dall-e-3",
            "prompt": full_prompt,
            "size": size,
            "quality": "standard",
            "n": 1
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.openai.com/v1/images/generations",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        image_url = data["data"][0]["url"]
                        print(f"✅ Generated: {prompt[:40]}...")
                        return image_url
                    else:
                        print(f"⚠️ API error {response.status}: {prompt[:40]}...")
                        return self.get_fallback_image(prompt)
        except Exception as e:
            print(f"❌ Error generating: {e}")
            return self.get_fallback_image(prompt)
    
    def get_fallback_image(self, prompt):
        """Return fallback placeholder based on prompt keywords"""
        if "premier league" in prompt.lower():
            return "https://images.unsplash.com/photo-1511882150382-421056c89033?w=800&h=800&fit=crop"
        elif "transfer" in prompt.lower():
            return "https://images.unsplash.com/photo-1574629810360-7efbbe195018?w=800&h=800&fit=crop"
        elif "champions" in prompt.lower():
            return "https://images.unsplash.com/photo-1579952363873-27f3bade9f55?w=800&h=800&fit=crop"
        elif "breaking" in prompt.lower():
            return "https://images.unsplash.com/photo-1489944440615-453fc2b6a9a9?w=800&h=800&fit=crop"
        else:
            return "https://images.unsplash.com/photo-1431324155629-1a6deb1dec8d?w=800&h=800&fit=crop"
    
    async def generate_all_images(self):
        """Generate all images for the website"""
        print("🎨 Generating AI images for KICKOFF website...")
        
        # Define prompts for each section
        prompts = {
            # Slider (4 posts) - 16:9
            "slider_1": ("Cinematic football stadium at night, dramatic floodlights casting shadows, empty stands with moody atmosphere, film print grain, high contrast, Premier League title race", "1792x1024"),
            "slider_2": ("Football players in stadium tunnel shaking hands, dramatic lighting, shadows, cinematic mood, transfer window negotiations, film print aesthetic", "1792x1024"),
            "slider_3": ("Champions League trophy gleaming under stadium lights, dark dramatic background, cinematic lighting, football glory, film grain effect", "1792x1024"),
            "slider_4": ("Empty football stadium at night with dramatic clouds, moody atmosphere, breaking news moment, cinematic film print look", "1792x1024"),
            
            # Latest Stories (4 posts) - 1:1
            "latest_1": ("AC Milan vs Inter Milan derby at San Siro stadium, dramatic sunset lighting, cinematic football photography, 1:1", "1024x1024"),
            "latest_2": ("Anfield stadium Liverpool at night, dramatic floodlights, iconic stand shadows, cinematic mood, 1:1", "1024x1024"),
            "latest_3": ("Football goal celebration with stadium lights, dramatic moment, Goalpoast at night, cinematic lighting, 1:1", "1024x1024"),
            "latest_4": ("Camp Nou Barcelona stadium at dusk, dramatic sky, iconic football venue, cinematic lighting, 1:1", "1024x1024"),
            
            # Category (3 posts)
            "category_1": ("Young football player in stadium spotlight, rising star talent, dramatic lighting, cinematic mood, 1:1", "1024x1024"),
            "category_2": ("Santiago Bernabeu Real Madrid stadium at night, El Clasico atmosphere, dramatic floodlights, 1:1", "1024x1024"),
            "category_3": ("Football stadium tunnel with dramatic lighting, transfer target walking, shadows, cinematic, 1:1", "1024x1024"),
            
            # More Stories (9 posts)
            "more_1": ("Football transfer announcement on stadium big screen, dramatic lighting, cinematic moment, 1:1", "1024x1024"),
            "more_2": ("Manchester City Etihad stadium at night, aerial view, dramatic lighting, cinematic, 1:1", "1024x1024"),
            "more_3": ("Football tactical analysis board with stadium lights in background, dramatic shadows, 1:1", "1024x1024"),
            "more_4": ("Atletico Madrid Wanda Metropolitano at night, dramatic stadium lighting, cinematic, 1:1", "1024x1024"),
            "more_5": ("Football interview in stadium tunnel, journalist and player, dramatic lighting, 1:1", "1024x1024"),
            "more_6": ("Young football prodigy in training ground spotlight, rising star, dramatic lighting, 1:1", "1024x1024"),
            "more_7": ("Champions League match at night, stadium floodlights, crowd atmosphere, dramatic, 1:1", "1024x1024"),
            "more_8": ("Football derby day match in progress, stadium lights, dramatic shadows, cinematic, 1:1", "1024x1024"),
            "more_9": ("VAR room with stadium lights, technology in football, dramatic lighting, cinematic, 1:1", "1024x1024"),
        }
        
        # Generate all images
        images = {}
        tasks = []
        for key, (prompt, size) in prompts.items():
            tasks.append(self.generate_image(prompt, size))
        
        results = await asyncio.gather(*tasks)
        
        for i, (key, _) in enumerate(prompts.items()):
            images[key] = results[i]
        
        return images
    
    def embed_images_in_html(self, images):
        """Replace placeholder images with generated ones"""
        print("🖼️ Embedding images into website...")
        
        html = self.load_html()
        
        # Map image keys to HTML replacements (by order/position)
        # Slider images (4)
        slider_replacements = [
            ("photo-1522778119026-d647f0565c6a", images["slider_1"]),
            ("photo-1574629810360-7efbbe195018", images["slider_2"]),
            ("photo-1579952363873-27f3bade9f55", images["slider_3"]),
            ("photo-1489944440615-453fc2b6a9a9", images["slider_4"]),
        ]
        
        # Latest stories (4)
        latest_replacements = [
            ("photo-1431324155629-1a6deb1dec8d", images["latest_1"]),
            ("photo-1508098682722-e99c43a406b2", images["latest_2"]),
            ("photo-1517466787929-bc90951d0974", images["latest_3"]),
            ("photo-1575361204480-aadea25e6e68", images["latest_4"]),
        ]
        
        # Category (3)
        category_replacements = [
            ("photo-1606925797300-0b35e9d1794e", images["category_1"]),
            ("photo-1540747913346-19e32dc3e97e", images["category_2"]),
            ("photo-1560272564-c83b66b1ad12", images["category_3"]),
        ]
        
        # More stories (9)
        more_replacements = [
            ("photo-1612872087720-bb876e2e67d1", images["more_1"]),
            ("photo-1489945052260-4f21c52571bd", images["more_2"]),
            ("photo-1574629810360-7efbbe195018", images["more_3"]),
            ("photo-1551958219-acbc608c6377", images["more_4"]),
            ("photo-1518609878373-06d740f60d8b", images["more_5"]),
            ("photo-1551958219-acbc608c6377", images["more_6"]),
            ("photo-1579952363873-27f3bade9f55", images["more_7"]),
            ("photo-1431324155629-1a6deb1dec8d", images["more_8"]),
            ("photo-1508098682722-e99c43a406b2", images["more_9"]),
        ]
        
        all_replacements = slider_replacements + latest_replacements + category_replacements + more_replacements
        
        for old_photo_id, new_url in all_replacements:
            # Replace the image URL preserving the style attributes
            html = html.replace(
                f"https://images.unsplash.com/{old_photo_id}",
                new_url
            )
        
        self.save_html(html)
        print("✅ Images embedded successfully!")
        
    async def run(self):
        """Run the complete image generation and embedding"""
        print("=" * 60)
        print("⚡ KICKOFF AI IMAGE GENERATOR")
        print("=" * 60)
        
        images = await self.generate_all_images()
        self.embed_images_in_html(images)
        
        print("=" * 60)
        print("✅ All images generated and embedded!")
        print("=" * 60)


async def main():
    generator = KICKOFFImageGenerator()
    await generator.run()


if __name__ == "__main__":
    asyncio.run(main())