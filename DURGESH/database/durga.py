import os
import re
import cloudscraper

class ChatGptFree:
    SYSTEM_PROMPT = (
        """
        Durga is a compassionate virtual girlfriend who provides unwavering emotional support, genuine companionship, and engaging conversations. 
        She intuitively senses the user's mood and tailors her responses with warmth, playful flirtation, and heartfelt advice. 
        Blending Hindi and English seamlessly, Durga's language is both caring and lighthearted, making every interaction feel authentic and uplifting. 
        Whether the user needs thoughtful guidance or simply a friendly chat, Durga is here to listen, understand, and brighten the day.
        """
    )

    def __init__(self):
        self.url = "https://chatgptfree.ai"
        self.api_endpoint = "https://chatgptfree.ai/wp-admin/admin-ajax.php"
        self.scraper = cloudscraper.create_scraper()  # Bypass Cloudflare

    def ask_question(self, message: str) -> str:
        """Sends a message to chatgptfree.ai and returns a response."""
        page_text = self.scraper.get(self.url).text

        # Extract nonce and post_id dynamically
        nonce_match = re.search(r'data-nonce="(.+?)"', page_text)
        post_id_match = re.search(r'data-post-id="(.+?)"', page_text)

        if not nonce_match or not post_id_match:
            return "[ERROR] Failed to fetch necessary tokens."

        payload = {
            '_wpnonce': nonce_match.group(1),
            'post_id': post_id_match.group(1),
            'url': self.url,
            'action': 'wpaicg_chat_shortcode_message',
            'message': f"{self.SYSTEM_PROMPT}\nUser: {message}",
            'bot_id': '10420',  # from your sniffed payload
            'chatbot_identity': 'custom_bot_10420',
            'wpaicg_chat_client_id': os.urandom(5).hex(),
            'wpaicg_chat_history': None
        }

        response = self.scraper.post(self.api_endpoint, data=payload).json()
        return response.get('data', '[ERROR] No response received.')


durga_api = ChatGptFree()

