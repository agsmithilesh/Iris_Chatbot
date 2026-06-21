import os
import requests
from dotenv import load_dotenv

load_dotenv()

MAX_CHARS = 8000

def paper_search(query):
    try:
        response = requests.get(
            "https://huggingface.co/api/papers/search",
            params={"q": query},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        results = []
        for item in data:
            paper = item.get("paper", item)  # handle both wrapped and unwrapped
            results.append({
                "id": paper.get("id", ""),
                "title": paper.get("title", ""),
                "snippet": paper.get("summary", "")[:300]
            })
        return results
    except Exception as e:
        return {"error": str(e)}
    
def normalize_id(s):
    s = s.strip()
    if "arxiv.org" in s:
        s = s.rstrip("/").split("/")[-1]
    s = s.split("v")[0]
    return s

def read_paper(url):
    arxiv_id = normalize_id(url)
    try:
        meta_response = requests.get(f"https://huggingface.co/api/papers/{arxiv_id}", timeout=10)
        meta_response.raise_for_status()
        meta = meta_response.json()
    except Exception as e:
        return {"error": f"could not fetch metadata: {str(e)}"}
    try:
        md_response = requests.get(f"https://huggingface.co/papers/{arxiv_id}.md", timeout=10)
        md_response.raise_for_status()
        content = md_response.text
    except Exception:
        content = meta.get("summary", "")

    if len(content) > MAX_CHARS:
        content = content[:MAX_CHARS] + "\n[...truncated]"

    return {
        "id": arxiv_id,
        "title": meta.get("title", ""),
        "content": content
    }
