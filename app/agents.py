import os
import json
from textwrap import dedent
from typing import List, Dict, Any

from agno.models.google import Gemini
from agno.agent import Agent
from agno.media import Image as AgnoImage
from agno.tools.tavily import TavilyTools

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

def _get_gemini() -> Gemini:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GOOGLE_API_KEY in environment.")
    return Gemini(id=GEMINI_MODEL, api_key=api_key)

def _get_tavily_tools() -> TavilyTools | None:
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return None
    return TavilyTools(api_key=api_key)

# ---- Análise multimodal por Agent (Agno way) ----
def analyze_with_gemini(image_path: str, prompt: str) -> str:
    model = _get_gemini()
    agent = Agent(model=model, markdown=False)
    res = agent.run(prompt, images=[AgnoImage(filepath=image_path)])
    # Em versões recentes, Agent.run retorna objeto com .content; se for string, tratamos igual
    text = getattr(res, "content", res)
    return (text or "").strip()

# ---- Pesquisa com Agent + TavilyTools (JSON estrito) ----
def research_references(analysis_text: str, max_results: int = 3) -> List[Dict[str, Any]]:
    tavily = _get_tavily_tools()
    if tavily is None:
        return []

    model = _get_gemini()
    agent = Agent(
        name="research_agent",
        role="Pesquisador médico",
        model=model,
        tools=[tavily],
        instructions=(
            "Você recebe um relatório de análise de imagem. "
            "Use a ferramenta de busca para encontrar 2-3 referências recentes e confiáveis "
            "(diretrizes, sociedades médicas, revisões). "
            "Responda ESTRITAMENTE em JSON com a chave 'references' que é uma lista de objetos "
            "no formato: [{\"title\":\"...\",\"url\":\"...\",\"snippet\":\"...\"}]. "
            f"Máximo de {max_results} itens. Texto em português. Sem comentários fora do JSON."
        ),
        expected_output=dedent("""
        {
          "references": [
            {"title": "string", "url": "string", "snippet": "string"}
          ]
        }
        """),
        markdown=False
    )

    user_msg = (
        "Relatório da análise de imagem:\n"
        f"{analysis_text}\n\n"
        "Gere as referências em JSON conforme instruído."
    )

    raw = agent.run(user_msg)
    text = getattr(raw, "content", raw)
    text = (text or "").strip()

    # Extrai JSON
    try:
        data = json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(text[start:end+1])
            except Exception:
                return []
        else:
            return []

    refs = data.get("references", [])
    norm = []
    for r in refs[:max_results]:
        norm.append({
            "title": (r.get("title") or "Fonte").strip(),
            "url": (r.get("url") or "").strip(),
            "content": (r.get("snippet") or r.get("content") or "").strip()[:400]
        })
    return norm
