import os
from dotenv import load_dotenv
from fasthtml.common import *
from starlette.responses import PlainTextResponse, FileResponse
from starlette.datastructures import UploadFile as StarletteUploadFile

from app.services.imaging import is_allowed_filename, save_upload_to_disk, STORAGE_DIR
from app.services.pipeline import run_pipeline
from app.utils import markdown_to_html, create_loading_overlay
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm

load_dotenv()

MAX_MB = int(os.getenv("APP_MAX_UPLOAD_MB", "7"))
MAX_BYTES = MAX_MB * 1024 * 1024

app = FastHTML()
rt = app.route

# ---------- Helpers UI ----------
# Header removido conforme solicitado

def UploadCard():
    # Form com auto-submit quando o input #file mudar (hx-trigger) e DnD via JS
    return Card(
        H2("📤 Enviar Imagem Médica", cls="card-title"),
        P(f"📋 Arraste e solte a imagem, ou clique para selecionar (JPG, JPEG, PNG, BMP, GIF — até {MAX_MB}MB).", cls="upload-instructions"),
        Form(
            # zona de drop: clica → abre seletor; drop → faz upload
            Div(
                Div("🖼️ Solte a imagem aqui ou clique para selecionar",
                    id="dropzone",
                    cls="dropzone enhanced-dropzone",
                    role="button",
                    tabindex="0",
                    onclick="document.getElementById('file').click();"),
                # barra de progresso do upload
                Div(
                    Div(id="upload-bar", cls="bar"),
                    id="upload-progress", cls="progress"
                ),
                # indicador de upload (aparece durante a requisição HTMX do form)
                Div(Span(cls="spinner"), " 📤 Enviando imagem...", id="upload-indicator", cls="htmx-indicator mt-8"),
                cls="stack"
            ),
            # input real (escondido). Quando muda, o form é enviado por HTMX
            Input(type="file", id="file", name="file", accept="image/*", required=True, style="display:none"),
            hx_post="/upload",
            hx_target="#stage",
            hx_swap="innerHTML",
            hx_indicator="#upload-indicator",
            hx_encoding="multipart/form-data",
            hx_trigger="change from:#file",
            cls="container upload-form"
        ),
        cls="container upload-card fade-in"
    )

def AnalysisActions(uid: str):
    return Div(
        # botão que dispara análise; indicador próprio e disable enquanto roda
        Div(
            Button("🔍 Analisar Imagem", id="analyze-btn", cls="primary analysis-btn",
                   hx_post=f"/analyze?uid={uid}",
                   hx_target="#stage",
                   hx_swap="innerHTML",
         hx_indicator="#analyze-indicator",
                   hx_disabled_elt="#analyze-btn",
             onclick="showLoadingOverlay()"),
            cls="cluster analysis-actions"
        ),
        cls="grid action-buttons"
    )

def PreviewCard(img_src_rel: str, uid: str, original_name: str):
    # Estrutura visual alinhada ao card de resultado
    return Card(
        H2("👀 Pré-visualização da Imagem", cls="report-title preview-title"),
        P(Strong("📁 Arquivo: "), original_name, cls="file-info"),
        Div(
            Div(
                Img(src=img_src_rel, alt="Pré-visualização da imagem médica", cls="preview-image"),
                cls="image-panel"
            ),
            cls="image-container"
        ),
    AnalysisActions(uid),
        cls="preview-card fade-in"
    )

def ResultCard(markdown_html: str, uid: str):
    # Converter markdown para HTML adequado
    html_content = markdown_to_html(markdown_html)
    
    return Card(
        H2("📋 Relatório de Análise", cls="report-title"),
        Div(
            Div(NotStr(html_content), cls="medical-report"),
            cls="medical-report-scroll"
        ),
        Div(
            A("📑 Baixar PDF", href=f"/download/{uid}.pdf", cls="primary button download-btn full-width action-lg"),
            cls="grid download-actions"
        ),
        cls="result-card fade-in"
    )

# Histórico removido

def Layout(*children):
    return Titled(
        "🩺 Analisador de Imagens Médicas - Diagnóstico por IA",
        Head(
            Meta(name="viewport", content="width=device-width, initial-scale=1.0"),
            Meta(name="description", content="Análise de imagens médicas com inteligência artificial"),
            Link(rel="stylesheet", href="https://unpkg.com/@picocss/pico@latest/css/pico.min.css"),
            Link(rel="stylesheet", href="/static/spinner.css"),
            Script(src="/static/dnd.js"),
            Script(src="https://unpkg.com/htmx.org@1.9.10/dist/htmx.min.js"),
            # Adicionar favicon
            Link(rel="icon", href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🩺</text></svg>"),
            # JavaScript para loading
                        Script("""
                                function showLoadingOverlay() {
                                    const indicator = document.getElementById('analyze-indicator');
                                    if (indicator) indicator.style.display = 'flex';
                                    document.body.classList.add('loading-locked');
                                }

                                // Exibir/ocultar loading automaticamente para requisições HTMX
                                document.addEventListener('htmx:beforeRequest', function(evt) {
                                    const indicator = document.getElementById('analyze-indicator');
                                    if (indicator) indicator.style.display = 'flex';
                                    document.body.classList.add('loading-locked');
                                });

                                document.addEventListener('htmx:afterRequest', function(evt) {
                                    const indicator = document.getElementById('analyze-indicator');
                                    if (indicator) indicator.style.display = 'none';
                                    document.body.classList.remove('loading-locked');
                                });
                        """)
        ),
                Main(*children, cls="container main-content"),
                # Loader global (fora dos cards para cobrir a página toda)
                NotStr(create_loading_overlay()),
        # Footer médico
        Footer(
            P("⚠️ Este sistema é uma ferramenta de apoio diagnóstico. Sempre consulte um profissional de saúde qualificado para decisões médicas.", cls="text-center medical-warning"),
            P("Desenvolvido com ❤️ para auxiliar profissionais de saúde", cls="text-center footer-credit"),
            cls="container medical-footer"
        )
    )

# ---------- Páginas ----------
@rt("/")
def index():
    return Layout(
        Div(id="stage")(
            UploadCard()
        )
    )

# Rotas de histórico e visualização removidas

# ---------- Rotas parciais (HTMX) ----------
@rt("/upload", methods=["POST"])
async def upload(file: StarletteUploadFile):
    if file is None or not getattr(file, "filename", ""):
        return Card(P("Nenhum arquivo enviado."), cls="container")

    if not is_allowed_filename(file.filename):
        return Card(P("Formato não suportado."), cls="container")

    raw = await file.read()
    if len(raw) > MAX_BYTES:
        return Card(P(f"Arquivo excede {MAX_MB}MB."), cls="container")

    uid, original_path = save_upload_to_disk(raw, file.filename)

    folder = os.path.join(STORAGE_DIR, uid)
    with open(os.path.join(folder, "name.txt"), "w", encoding="utf-8") as f:
        f.write(file.filename)

    from app.services.imaging import preprocess_image
    processed_path = preprocess_image(original_path)

    rel_src = f"/staticfile/{uid}/processed.jpg"
    return Div(
        PreviewCard(rel_src, uid, file.filename)
    )

@rt("/staticfile/{uid}/{fname}")
def staticfile(uid: str, fname: str):
    if "/" in uid or "/" in fname or ".." in uid or ".." in fname:
        return PlainTextResponse("Caminho inválido.", status_code=400)
    path = os.path.join(STORAGE_DIR, uid, fname)
    if not os.path.exists(path):
        return PlainTextResponse("Arquivo não encontrado.", status_code=404)
    return FileResponse(path, headers={"Cache-Control": "no-cache"})

@rt("/analyze", methods=["POST"])
def analyze(uid: str):
    folder = os.path.join(STORAGE_DIR, uid)
    if not os.path.isdir(folder):
        return Card(P("Sessão não encontrada."), cls="container")

    processed = os.path.join(folder, "processed.jpg")
    if not os.path.exists(processed):
        for fname in os.listdir(folder):
            if fname.startswith("original"):
                processed = os.path.join(folder, fname)
                break

    if not os.path.exists(processed):
        return Card(P("Imagem não encontrada para análise."), cls="container")

    original_name = "-"
    name_file = os.path.join(folder, "name.txt")
    if os.path.exists(name_file):
        with open(name_file, "r", encoding="utf-8") as f:
            original_name = f.read().strip() or "-"

    try:
        result = run_pipeline(processed)
    except Exception as e:
        return Card(
            H2("Erro durante a análise"),
            P(f"{e}"),
            A("Voltar", href="/", cls="secondary")
        )

    md_path = os.path.join(folder, "report.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(result["markdown"])

    # Nenhum armazenamento em banco: usuário fará o download se desejar

    # imagem processada relativa
    rel_img_src = f"/staticfile/{uid}/processed.jpg" if os.path.exists(processed) else ""

    return Div(
        Div(
            Div(
        Card(
                    H2("👀 Pré-visualização da Imagem", cls="report-title preview-title"),
                    Div(
                        (Img(src=rel_img_src, alt="Imagem processada", cls="preview-image") if rel_img_src else P("Imagem não disponível.")),
                        cls="image-panel"
                    ),
                    Div(
            A("🆕 Nova análise", href="/", cls="secondary button full-width action-lg new-analysis-btn"),
                        cls="mt-4"
                    )
                ),
                cls="analysis-image"
            ),
            Div(
                ResultCard(result["markdown"], uid),
                cls="analysis-report"
            ),
            cls="analysis-grid"
        )
    )

@rt("/download/{uid}.md")
def download_md(uid: str):
    folder = os.path.join(STORAGE_DIR, uid)
    md_path = os.path.join(folder, "report.md")
    if not os.path.exists(md_path):
        return PlainTextResponse("Relatório não encontrado.", status_code=404)
    return FileResponse(md_path, media_type="text/markdown", filename=f"relatorio-{uid}.md")

@rt("/download/{uid}.pdf")
def download_pdf(uid: str):
    folder = os.path.join(STORAGE_DIR, uid)
    md_path = os.path.join(folder, "report.md")
    if not os.path.exists(md_path):
        return PlainTextResponse("Relatório não encontrado.", status_code=404)
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    out_path = os.path.join(STORAGE_DIR, uid, "report.pdf")
    page_w, page_h = A4
    margin = 2 * cm
    y = page_h - margin

    c = canvas.Canvas(out_path, pagesize=A4)
    c.setTitle("Relatório de Análise de Imagem Médica")
    c.setFont("Helvetica-Bold", 14)
    c.drawString(margin, y, "Relatório de Análise de Imagem Médica")
    y -= 1.0 * cm
    c.setFont("Helvetica", 11)

    import textwrap
    for block in content.splitlines():
        if not block.strip():
            y -= 0.55 * cm
            continue
        for line in textwrap.wrap(block, width=100):
            if y < margin + 1.0 * cm:
                c.showPage()
                c.setFont("Helvetica", 11)
                y = page_h - margin
            c.drawString(margin, y, line)
            y -= 0.55 * cm

    c.showPage()
    c.save()

    return FileResponse(out_path, media_type="application/pdf", filename=f"relatorio-{uid}.pdf")

# Rota de exclusão removida

@rt("/static/{fname:path}")
def static(fname: str):
    base = os.path.join(os.path.dirname(__file__), "static")
    path = os.path.join(base, fname)
    if not os.path.abspath(path).startswith(os.path.abspath(base)):
        return PlainTextResponse("Caminho inválido.", status_code=400)
    if not os.path.exists(path):
        return PlainTextResponse("Arquivo não encontrado.", status_code=404)
    return FileResponse(path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=5001, reload=True)
