from app.services.chat_service import ChatService
from sqlalchemy.ext.asyncio import AsyncSession


class VoiceChatService(ChatService):
    """
    Voice-specific chat service with shorter responses.
    Inherits from ChatService but modifies responses for voice.
    """
    
    def __init__(self, db: AsyncSession):
        super().__init__(db)
    
    async def send_message(
        self,
        conversation_id: str,
        user_message: str
    ) -> dict:
        """Process message and shorten response for voice."""
        
        # Get normal response
        result = await super().send_message(conversation_id, user_message)
        
        # Shorten response for voice
        response = result.get("response", "")
        response = self._shorten_for_voice(response)
        result["response"] = response
        
        return result
    
    def _shorten_for_voice(self, text: str) -> str:
        """Make response suitable for voice (shorter, no markdown)."""
        
        # Remove markdown formatting
        text = text.replace("**", "")
        text = text.replace("*", "")
        text = text.replace("•", "-")
        text = text.replace("\n\n", ". ")
        text = text.replace("\n", ". ")
        
        # Remove bullet points formatting
        lines = text.split(". ")
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if line.startswith("- "):
                line = line[2:]
            if line:
                cleaned_lines.append(line)
        
        text = ". ".join(cleaned_lines)
        
        # Limit length for voice (keep under 200 characters if possible)
        if len(text) > 300:
            # Find a good breaking point
            sentences = text.split(". ")
            short_text = ""
            for sentence in sentences:
                if len(short_text) + len(sentence) < 250:
                    short_text += sentence + ". "
                else:
                    break
            text = short_text.strip()
        
        return text