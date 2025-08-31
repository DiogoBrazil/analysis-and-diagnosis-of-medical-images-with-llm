import re

def markdown_to_html(text: str) -> str:
    """Converte um subconjunto de Markdown para HTML estável e limpo.

    Objetivos:
    - Cabeçalhos #, ##, ###
    - Listas com "- " e listas numeradas "1. " (agrupando itens contíguos)
    - Parágrafos e quebras de linha
    - Links HTTP/S transformados em <a>
    - Mantém o conteúdo previsível para estilização (.medical-report)
    """
    if not text:
        return ""

    lines = [l.rstrip() for l in text.splitlines()]
    html_parts = []
    in_ul = False
    in_ol = False

    def close_lists():
        nonlocal in_ul, in_ol
        if in_ul:
            html_parts.append("</ul>")
            in_ul = False
        if in_ol:
            html_parts.append("</ol>")
            in_ol = False

    header_re = re.compile(r"^(#{1,3})\s+(.*)$")
    ol_re = re.compile(r"^\s*(\d+)\.\s+(.*)$")
    ul_re = re.compile(r"^\s*[-•]\s+(.*)$")
    url_re = re.compile(r"(https?://[^\s<>'\)\]]+)")
    bold_re = re.compile(r"\*\*(.+?)\*\*")
    italic_re = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")

    def apply_inline(s: str) -> str:
        # Ordem: bold -> italic -> links
        s = bold_re.sub(r"<strong>\1</strong>", s)
        s = italic_re.sub(r"<em>\1</em>", s)
        s = url_re.sub(r'<a href="\1" target="_blank" class="reference-link">\1</a>', s)
        return s

    paragraph_buf = []

    def flush_paragraph():
        nonlocal paragraph_buf
        if paragraph_buf:
            content = " ".join(paragraph_buf).strip()
            if content:
                html_parts.append(f"<p>{apply_inline(content)}</p>")
        paragraph_buf = []

    for raw in lines:
        line = raw.strip()
        # linha vazia encerra parágrafo e listas seguem abertas
        if not line:
            flush_paragraph()
            continue

        m = header_re.match(line)
        if m:
            flush_paragraph()
            close_lists()
            level = len(m.group(1))
            content = apply_inline(m.group(2))
            html_parts.append(f"<h{level}>{content}</h{level}>")
            continue

        m = ol_re.match(line)
        if m:
            flush_paragraph()
            if in_ul:
                html_parts.append("</ul>")
                in_ul = False
            if not in_ol:
                html_parts.append("<ol>")
                in_ol = True
            html_parts.append(f"<li>{apply_inline(m.group(2))}</li>")
            continue

        m = ul_re.match(line)
        if m:
            flush_paragraph()
            if in_ol:
                html_parts.append("</ol>")
                in_ol = False
            if not in_ul:
                html_parts.append("<ul>")
                in_ul = True
            html_parts.append(f"<li>{apply_inline(m.group(1))}</li>")
            continue

        # linha normal acumula em parágrafo
        paragraph_buf.append(line)

    flush_paragraph()
    close_lists()

    return "".join(html_parts)

def create_loading_overlay() -> str:
    """Retorna o HTML bruto do loader de batimento cardíaco.

    É inserido na página envolvido por NotStr no arquivo main.py.
    """
    return (
        '<div id="analyze-indicator" class="htmx-indicator loading-overlay">'
        '  <div class="hr-box">'
        '    <div class="hr-loader-container">'
        '      <div class="heart-rate">'
        '        <svg viewBox="0 0 150 73" width="140" height="68" xmlns="http://www.w3.org/2000/svg">'
        '          <polyline points="0,45.486 38.514,45.486 44.595,33.324 50.676,45.486 57.771,45.486 62.838,55.622 71.959,9 80.067,63.729 84.122,45.486 97.297,45.486 103.379,40.419 110.473,45.486 150,45.486" stroke="#009B9E" stroke-width="3" fill="none" stroke-miterlimit="10" />'
        '        </svg>'
        '        <div class="fade-in"></div>'
        '        <div class="fade-out"></div>'
        '      </div>'
        '    </div>'
        '    <div class="hr-text">Analisando imagem médica...</div>'
        '  </div>'
        '</div>'
    )
