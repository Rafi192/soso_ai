
import re

class ResponseFormatter:

    MAX_WHATSAPP_LENGTH =  1600    
    
    
    @staticmethod
    def format_text(raw_response:str) -> str:

        text = raw_response.strip()
        text = ResponseFormatter.remove_markdown(text)
        text = ResponseFormatter.truncate(text)

        return text
    

    @staticmethod
    def remove_markdown(text:str) -> str:
        #WhatsApp doesn't render markdown — so,
        #raw asterisks, hashes, and underscores
        text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)   # bold
        text = re.sub(r"\*(.*?)\*", r"\1", text)        # italic
        text = re.sub(r"#{1,6}\s*", "", text)            # headers
        text = re.sub(r"`(.*?)`", r"\1", text)           # inline code
        return text
    
    @staticmethod 
    def truncate(text:str) -> str:
        if len(text) <= ResponseFormatter.MAX_WHATSAPP_LENGTH:
            return text
 
        truncated = text[:ResponseFormatter.MAX_WHATSAPP_LENGTH]
        
        last_period = truncated.rfind(".")
        if last_period > ResponseFormatter.MAX_WHATSAPP_LENGTH * 0.7:
            return truncated[:last_period + 1]
        return truncated