import asyncio, os, aiohttp, aiofiles
from typing import List
from pyrogram import filters
from DURGESH import app

# AI Image Generator Class
class AIImageGenerator:
    """Asynchronous AI Image Generator using Artbit API."""

    def init(self, timeout: int = 60, output_dir: str = "images"):
        self.url = "https://artbit.ai/api/generateImage"
        self.headers = {
            "User-Agent": "DurgeshImageBot/1.0",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        self.timeout = timeout
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    async def generate_images(self, prompt: str, amount: int = 5) -> List[str]:
        """Generates AI images asynchronously and returns their URLs."""
        payload = {
            "captionInput": prompt,
            "selectedSamples": str(amount)
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.url,
                json=payload,
                headers=self.headers,
                timeout=self.timeout
            ) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                return data.get("imgs", [])

    async def download_images(self, img_urls: List[str]) -> List[str]:
        """Downloads and saves generated images asynchronously."""
        saved_files = []
        async with aiohttp.ClientSession() as session:
            tasks = []
            for i, img_url in enumerate(img_urls):
                filename = os.path.join(self.output_dir, f"image_{i+1}.png")
                tasks.append(self._download_image(session, img_url, filename))
                saved_files.append(filename)
            await asyncio.gather(*tasks)
        return saved_files

    async def _download_image(self, session, url: str, filename: str):
        """Helper function to download and save a single image."""
        async with session.get(url, timeout=self.timeout) as resp:
            if resp.status != 200:
                return
            async with aiofiles.open(filename, "wb") as file:
                await file.write(await resp.read())

# Initialize AI Image Generator
image_generator = AIImageGenerator()
