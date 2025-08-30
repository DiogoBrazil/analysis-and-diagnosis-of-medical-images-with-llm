import os
from dotenv import load_dotenv
import uvicorn
from fasthtml.common import *
from starlette.responses import PlainTextResponse, FileResponse
from starlette.datastructures import UploadFile as StarletteUploadFile
from app.services.imaging import is_allowed_filename, save_upload_to_disk, STORAGE_DIR
from app.services.pipeline import run_pipeline
from app.services.db import save_analysis, list_analyses, get_analysis, delete_analysis
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm

load_dotenv()

MAX_MB = int(os.getenv("APP_MAX_UPLOAD_MB", "7"))
MAX_BYTES = MAX_MB * 1024 * 1024

app = FastHTML()
rt = app.route

def HeaderBar():
    return Header(
        Nav(
            Ul(
                Li(A("Início", href="/")),
                Li(A("Histórico", href="/history")),
                Li(Button("Modo escuro", type="button", onclick="toggleTheme()", cls="secondary outline")),
            ),
        ),
        H1("Analisador de Imagens Médicas"),
        P("Resultados não substituem avaliação profissional.", cls="contrast"),
        cls="container"
    )

def UploadCard():
    return Card(
        H2("Enviar imagem"),
        P(f"Formatos aceitos: JPG, JPEG, PNG, BMP, GIF (até {MAX_MB}MB)."),
        Form(
            Input(type="file", name="file", accept="image/*", required=True),
            Div(
                Button("Carregar", type="submit", cls="primary"),
                Span(Span(cls="spinner"), " Processando…", cls="htmx-indicator"),
                cls="grid"
            ),
            hx_post="/upload", hx_target="#stage", hx_swap="innerHTML", hx_indicator=".htmx-indicator"
        ),
        cls="container"
    )

def AnalysisActions(uid: str):
    return Div(
        Button("Analisar", cls="primary",
               hx_post=f"/analyze?uid={uid}",
               hx_target="#stage",
               hx_swap="innerHTML",
               hx_indicator=".htmx-indicator"),
        A("Nova análise", href="/", cls="secondary outline"),
        cls="grid"
    )

def PreviewCard(img_src_rel: str, uid: str, original_name: str):
    return Card(
        H2("Pré-visualização"),
        P(Strong("Arquivo: "), original_name),
        Img(src=img_src_rel, alt="Pré-visualização", style="max-width:100%; height:auto; border-radius:8px;"),
        AnalysisActions(uid)
    )

def ResultCard(markdown_html: str, uid: str):
    return Card(
        H2("Relatório"),
        Div(NotStr(markdown_html), style="max-width:900px;"),
        Div(
            A("Baixar relatório (.md)", href=f"/download/{uid}.md", cls="primary"),
            A("Baixar PDF", href=f"/download/{uid}.pdf", cls="secondary"),
            A("Nova análise", href="/", cls="contrast outline"),
            cls="grid"
        )
    )


def HistoryList(items):
    if not items:
        return Card(P("Nenhuma análise encontrada."), cls="container")
    rows = []
    for it in items:
        rows.append(
            Tr(
                Td(it["created_at"].replace("T", " ").split(".")[0]),
                Td(it["original_name"]),
                Td(
                    A("Abrir", href=f"/view/{it['id']}", cls="primary"),
                    " ",
                    A("Baixar .md", href=f"/download/{it['id']}.md"),
                    " ",
                    A("Baixar .pdf", href=f"/download/{it['id']}.pdf"),
                    " ",
                    Button("Excluir", cls="secondary outline",
                           hx_post=f"/delete/{it['id']}",
                           hx_confirm="Tem certeza que deseja excluir?",
                           hx_target="#history",
                           hx_swap="innerHTML")
                )
            )
        )
    return Card(
        H2("Histórico de análises"),
        Table(
            Thead(Tr(Th("Data"), Th("Arquivo"), Th("Ações"))),
            Tbody(*rows)
        ),
        cls="container"
    )

def Layout(*children):
    return Titled(
        "Analisador de Imagens Médicas",
        Head(
            Link(rel="stylesheet", href="https://unpkg.com/@picocss/pico@latest/css/pico.min.css"),
            Link(rel="stylesheet", href="/static/spinner.css"),
            Script(src="/static/theme.js"),
        ),
        HeaderBar(),
        Main(*children, cls="container")
    )

@rt("/")
def index():
    return Layout(
        Div(id="stage")(
            UploadCard()
        )
    )

@rt("/history")
def history():
    items = list_analyses(limit=50)
    return Layout(
        Div(id="history")(
            HistoryList(items)
        )
    )

@rt("/view/{uid}")
def view(uid: str):
    rec = get_analysis(uid)
    if not rec:
        return Layout(Card(P("Registro não encontrado."), cls="container"))
    if not rec["md_path"] or not os.path.exists(rec["md_path"]):
        return Layout(Card(P("Relatório não encontrado."), cls="container"))

    with open(rec["md_path"], "r", encoding="utf-8") as f:
        md = f.read()

    md_html = (
        md.replace("\n\n", "<br><br>")
          .replace("\n", "<br>")
          .replace("# Relatório de Análise de Imagem Médica", "<h2>Relatório de Análise de Imagem Médica</h2>")
          .replace("## 📋 Resultado da Análise", "<h3>📋 Resultado da Análise</h3>")
          .replace("## 📚 Referências", "<h3>📚 Referências</h3>")
    )

    img_src = ""
    if rec["processed_path"] and os.path.exists(rec["processed_path"]):
        fname = os.path.basename(rec["processed_path"])
        img_src = f"/staticfile/{uid}/{fname}"

    return Layout(
        Section(
            Div(
                Div(
                    (Img(src=img_src, alt="Imagem processada", style="width:100%;border-radius:8px;") if img_src else P("Imagem não disponível.")),
                    cls="col"
                ),
                Div(ResultCard(md_html, uid), cls="col"),
                cls="grid"
            ),
        )
    )

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

    save_analysis(
        uid=uid,
        original_name=original_name,
        processed_path=processed,
        md_path=md_path,
        analysis_text=result["analysis"],
        refs=result["references"]
    )

    md_html = (
        result["markdown"]
            .replace("\n\n", "<br><br>")
            .replace("\n", "<br>")
            .replace("# Relatório de Análise de Imagem Médica", "<h2>Relatório de Análise de Imagem Médica</h2>")
            .replace("## 📋 Resultado da Análise", "<h3>📋 Resultado da Análise</h3>")
            .replace("## 📚 Referências", "<h3>📚 Referências</h3>")
    )

    return Div(
        ResultCard(md_html, uid)
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
    rec = get_analysis(uid)
    if not rec or not rec.get("md_path") or not os.path.exists(rec["md_path"]):
        return PlainTextResponse("Relatório não encontrado.", status_code=404)
    with open(rec["md_path"], "r", encoding="utf-8") as f:
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

@rt("/delete/{uid}", methods=["POST"])
def delete(uid: str):
    delete_analysis(uid)
    items = list_analyses(limit=50)
    return Div(id="history")(
        HistoryList(items)
    )

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
    uvicorn.run("app.main:app", host="0.0.0.0", port=5001, reload=True)
