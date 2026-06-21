import os
import requests
import trafilatura
import json
import asyncio
from openai import OpenAI
from dotenv import load_dotenv
import httpx
from mcp import ClientSession
from mcp.client.auth import OAuthClientProvider, TokenStorage
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata, OAuthToken
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer, Input, RichLog
from textual.containers import Vertical

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],)

TOKEN_FILE = ".alphaxiv_tokens.json"
MODEL = "openai/gpt-oss-120b:free"
SERPER_API_KEY = os.environ["SERPER_API_KEY"]
MAX_CHARS = 800
MCP_SERVER_URL = "https://api.alphaxiv.org/mcp/v1"
REDIRECT_URI = "http://localhost:8765/callback"

def web_search(query):
    try:
        response = requests.post(
        "https://google.serper.dev/search",
        headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
        json={"q": query, "num":5},
        timeout=10,)
        response.raise_for_status()    # WEB SEARCH
        data = response.json()
        results = []
        for item in data.get("organic", []):
            results.append({
                            "title": item.get("title", ""),
                            "link": item.get("link", ""),
                            "snippet": item.get("snippet", ""),})
        return results
    except Exception as e:
            return {"error": f"could not fetch the page {str(e)}"}
    
def web_fetch(url):
    headers = {"User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0)"}
    response = requests.get(url, headers=headers,timeout=10)
    response.raise_for_status()                                  # WEB FETCH
    return response.text

def fetch_clean(url):
    html = web_fetch(url)
    text = trafilatura.extract(html, include_comments=False, include_tables=True)
    return text or ""

def clean_web_fetch(url):
    text = fetch_clean(url)
    if(len(text))>=MAX_CHARS:
        text = text[:MAX_CHARS]
    return(text)