# IRIS (Week-1)
A terminal-based AI chatbot built with Python and OpenRouter API.

## Features
#### Detective personality
- Gave Iris a detective personality using a system prompt.
#### Multi-turn conversation with memory
- Maintained a `messages` list and sent the full history 
on every API call so the AI remembers previous turns.
#### Token tracking
- printed token usage after every turn
#### Rolling buffer for long conversations + Auto Summary
- Set `MAX_TURNS = 5`
- When conversation hits 5 turns, older messages are 
  automatically summarised into one context message
- This keeps token usage low while maintaining coherence

### 1. Setup
- Created a project folder `my_chatbot`
- Stored API key safely in `.env` file
- Used `.gitignore` to prevent key from uploading to GitHub

### 2. Connecting to the AI
- Used OpenRouter API with the `openai` Python SDK
- Model used: `openai/gpt-oss-120b:free`