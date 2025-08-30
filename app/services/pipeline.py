from typing import Dict
from app.services.imaging import preprocess_image
from app.agents import analyze_with_gemini, research_references
from app.prompts import PROMPT_ANALYSIS

def run_pipeline(image_path: str) -> Dict:
    """
    1) Pré-processa
    2) Analisa com Agno Agent (Gemini multimodal)
    3) Pesquisa referências com Agent + TavilyTools (JSON)
    4) Agrega markdown final
    """
    processed_path = preprocess_image(image_path)
    analysis = analyze_with_gemini(processed_path, PROMPT_ANALYSIS)
    refs = research_references(analysis, max_results=3)

    md = ["# Relatório de Análise de Imagem Médica\n"]
    md.append("## 📋 Resultado da Análise\n")
    md.append(analysis.strip() + "\n")

    if refs:
        md.append("## 📚 Referências\n")
        for i, r in enumerate(refs, 1):
            title = r.get("title", f"Referência {i}")
            url = r.get("url", "")
            snippet = r.get("content", "")
            md.append(f"- **{title}** — {snippet}  \n  {url}")
    else:
        md.append("## 📚 Referências\n- Não foram recuperadas referências (Tavily desativado ou sem resultados).")

    return {
        "processed_path": processed_path,
        "analysis": analysis,
        "references": refs,
        "markdown": "\n".join(md)
    }
