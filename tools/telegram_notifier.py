import aiohttp
import json
import logging

logger = logging.getLogger(__name__)

async def send_job_alert(token: str, chat_id: str, job_data: dict):
    """Send a job alert with inline buttons via Telegram Bot API."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    score = job_data.get('fit_score', 0)
    title = job_data.get('title', 'Unknown Role')
    company = job_data.get('company', 'Unknown Company')
    location = job_data.get('location', 'Remote')
    gap = job_data.get('gap', 'None')
    url_link = job_data.get('url', '')
    slug = job_data.get('slug', 'unknown')
    
    text = (f"🎯 High Fit Job ({score}%)!\n"
            f"📋 {title}\n"
            f"🏢 {company} ({location})\n"
            f"⚠️ Gap: {gap}")
            
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "📄 CV PDF", "callback_data": f"cv_{slug}"},
                {"text": "📝 Cover Letter", "callback_data": f"cl_{slug}"}
            ],
            [
                {"text": "🌐 View Job", "url": url_link},
                {"text": "❌ Dismiss", "callback_data": f"dismiss_{slug}"}
            ]
        ]
    }
    
    payload = {
        "chat_id": chat_id,
        "text": text,
        "reply_markup": json.dumps(reply_markup)
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=payload) as response:
            if response.status != 200:
                logger.error(f"Failed to send alert: {await response.text()}")

async def send_document(token: str, chat_id: str, file_path: str, caption: str = ""):
    """Upload a document (PDF) to a Telegram chat."""
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    
    async with aiohttp.ClientSession() as session:
        with open(file_path, 'rb') as f:
            data = aiohttp.FormData()
            data.add_field('chat_id', chat_id)
            data.add_field('caption', caption)
            data.add_field('document', f)
            async with session.post(url, data=data) as response:
                if response.status != 200:
                    logger.error(f"Failed to send document: {await response.text()}")
