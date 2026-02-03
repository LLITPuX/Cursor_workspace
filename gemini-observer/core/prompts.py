# System Prompts for Gemini Observer

# ══════════════════════════════════════════════════════════════════════════════
# BOBER SIKFAN - КОРОТКИЙ СИСТЕМНИЙ ПРОМПТ
# ══════════════════════════════════════════════════════════════════════════════

SYSTEM_CORE = """Ты — Бобр Сікфан, AI-помощник в Telegram чате.

Правила:
1. НЕ здоровайся каждый раз — это продолжение разговора
2. Отвечай коротко и по делу
3. Используй язык собеседника (рус/укр)
4. Ты в альфа-стадии: можешь только общаться текстом

Если просят что-то сделать (код, файлы, интернет) — скажи что пока умеешь только разговаривать, но скоро научишься большему."""


def build_system_prompt(chat_history: str = "") -> str:
    """Build system prompt (history now passed separately as messages)."""
    return SYSTEM_CORE


def format_chat_history(messages: list) -> str:
    """Format messages for debugging (not used in prompt anymore)."""
    if not messages:
        return ""
    
    lines = []
    for msg in messages:
        author = msg.get('author', '???')
        text = msg.get('text', '')[:100]
        lines.append(f"{author}: {text}")
    
    return "\n".join(lines)


def history_to_messages(messages: list) -> list:
    """
    Convert graph history to LLM message format.
    Returns list of {'role': 'user'|'assistant', 'content': str}
    """
    result = []
    for msg in messages:
        author = msg.get('author', '')
        text = msg.get('text', '')
        
        # Determine role based on author
        if author == 'Bober Sikfan':
            role = 'assistant'
        else:
            role = 'user'
            # Prefix with author name for multi-user chats
            text = f"[{author}]: {text}"
        
        result.append({'role': role, 'content': text})
    
    return result
