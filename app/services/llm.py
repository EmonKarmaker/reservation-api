import json
from openai import AsyncOpenAI
from app.core.config import settings

# Initialize OpenAI client
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


async def call_llm(
    system_prompt: str,
    user_message: str,
    temperature: float = 0.7,
    model: str = "gpt-4o-mini"
) -> str:
    """
    Call OpenAI API and return the response text.
    
    Args:
        system_prompt: Instructions for the AI (who it is, how to behave)
        user_message: The user's message to respond to
        temperature: Creativity level (0=deterministic, 1=creative)
        model: Which OpenAI model to use
    
    Returns:
        The AI's response as a string
    """
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        temperature=temperature
    )
    
    return response.choices[0].message.content


async def call_llm_with_history(
    system_prompt: str,
    messages: list[dict],
    temperature: float = 0.7,
    model: str = "gpt-4o-mini"
) -> str:
    """
    Call OpenAI API with full conversation history.
    
    Args:
        system_prompt: Instructions for the AI
        messages: List of {"role": "user"|"assistant", "content": "..."} 
        temperature: Creativity level
        model: Which OpenAI model to use
    
    Returns:
        The AI's response as a string
    """
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    
    response = await client.chat.completions.create(
        model=model,
        messages=full_messages,
        temperature=temperature
    )
    
    return response.choices[0].message.content


async def extract_json_from_llm(
    system_prompt: str,
    user_message: str,
    temperature: float = 0.0,
    model: str = "gpt-4o-mini"
) -> dict:
    """
    Call OpenAI API and parse the response as JSON.
    Used for structured extraction (intents, entities, etc.)
    
    Args:
        system_prompt: Instructions that tell AI to respond in JSON
        user_message: The message to analyze
        temperature: Use 0 for deterministic extraction
        model: Which OpenAI model to use
    
    Returns:
        Parsed JSON as a dictionary
    """
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        temperature=temperature,
        response_format={"type": "json_object"}
    )
    
    content = response.choices[0].message.content
    
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"error": "Failed to parse JSON", "raw": content}