# main.py  ─ FastAPI versão do seu enviar_pdf

import os
import base64
import smtplib
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from starlette.responses import JSONResponse

app = FastAPI()

# ──────────────── 1.  Config  ────────────────
NOTION_TOKEN        = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID  = os.getenv("NOTION_DATABASE_ID")
ZAPI_INSTANCE_ID    = os.getenv("ZAPI_INSTANCE_ID")
ZAPI_TOKEN          = os.getenv("ZAPI_TOKEN")
ZAPI_SECURITY_TOKEN = os.getenv("ZAPI_SECURITY_TOKEN")
SMTP_SERVER         = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT           = int(os.getenv("SMTP_PORT", 587))
SMTP_USER           = os.getenv("SMTP_USER")
SMTP_PASSWORD       = os.getenv("SMTP_PASSWORD")

PACKAGE_FILE_MAPPING = {
    "Light Trimestral": "https://www.dropbox.com/scl/fi/q0j1xafp0y30hb4ntyb63/Light-Trimestral.pdf?rlkey=qc63z1mbghtc6q3cjduubdj4y&dl=1",
    "VIP Anual":       "https://www.dropbox.com/scl/fi/1fc7t8a84xoinz8zao7ww/VIP-Anual.pdf?rlkey=78zja6dk&dl=1",
}

# ──────────────── 2.  Helpers  ────────────────
def notion_latest_row() -> dict:
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type":  "application/json",
    }
    r = requests.post(url, headers=headers, timeout=15)
    if r.ok and r.json().get("results"):
        return r.json()["results"][0]
    raise RuntimeError(f"Notion query failed → {r.status_code} {r.text}")

def download_pdf(url: str) -> bytes:
    r = requests.get(url, timeout=60)
    if r.ok:
        return r.content
    raise RuntimeError(f"Download failed → {r.status_code}")

def send_whatsapp(phone: str, caption: str, file_bytes: bytes, filename: str):
    # texto
    requests.post(
        f"https://api.z-api.io/instances/{ZAPI_INSTANCE_ID}/token/{ZAPI_TOKEN}/send-text",
        json={"phone": phone, "message": caption},
        headers={"Client-Token": ZAPI_SECURITY_TOKEN},
        timeout=15,
    )
    # documento
    encoded = base64.b64encode(file_bytes).decode()
    ext = filename.split(".")[-1]
    r = requests.post(
        f"https://api.z-api.io/instances/{ZAPI_INSTANCE_ID}/token/{ZAPI_TOKEN}/send-document/{ext}",
        json={
            "phone": phone,
            "document": f"data:application/pdf;base64,{encoded}",
            "fileName": filename,
        },
        headers={"Client-Token": ZAPI_SECURITY_TOKEN},
        timeout=30,
    )
    if not r.ok:
        raise RuntimeError(f"WhatsApp error → {r.status_code} {r.text}")

def send_email(to_addr: str, subject: str, body_html: str, file_bytes: bytes, filename: str):
    msg = MIMEMultipart()
    msg["From"], msg["To"], msg["Subject"] = SMTP_USER, to_addr, subject
    msg.attach(MIMEText(body_html, "html"))
    part = MIMEApplication(file_bytes, Name=filename)
    part["Content-Disposition"] = f'attachment; filename="{filename}"'
    msg.attach(part)

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)

# ──────────────── 3.  Payload schema (opcional) ────────────────
class ManualPayload(BaseModel):
    email: str | None = None
    phone: str | None = None
    full_name: str | None = None
    pacote: str | None = None

# ──────────────── 4.  Endpoints ────────────────
@app.post("/enviar_pdf")
def enviar_pdf(payload: ManualPayload | None = None):
    """
    • Se payload vier no corpo, usamos ele.  
    • Caso contrário buscamos o registro mais recente no Notion.
    """
    try:
        if payload and payload.email:
            email      = payload.email
            phone      = payload.phone
            full_name  = payload.full_name or ""
            pacote     = payload.pacote or "Arquivo"
        else:
            row   = notion_latest_row()
            props = row["properties"]

            email      = props.get("Email", {}).get("email", "")

            phone_rich = props.get("Telefone", {}).get("rich_text", [])
            phone      = phone_rich[0].get("plain_text", "") if phone_rich else ""

            title_rich = props.get("Cliente", {}).get("title", [])
            full_name  = title_rich[0].get("plain_text", "") if title_rich else ""

            # CORRIGIDO: lê da propriedade "Pacote" (tipo SELECT)
            pacote_field = props.get("Pacote", {}).get("select", {})
            pacote       = pacote_field.get("name", "Arquivo")

        # Validação
        if not all([email, phone, full_name, pacote]):
            raise ValueError("Campos obrigatórios faltando (email, phone, nome ou pacote)")

        # Valida pacote
        pdf_url = PACKAGE_FILE_MAPPING.get(pacote)
        if not pdf_url:
            raise ValueError(f"Link do pacote '{pacote}' não encontrado")

        # Baixa PDF e monta mensagem
        pdf_bytes = download_pdf(pdf_url)
        filename  = f"{pacote}.pdf"
        first     = full_name.split()[0]
        caption   = f"Oi {first}, aqui está o PDF do seu investimento. Qualquer dúvida, me avise!"

        # Envia por WhatsApp
        send_whatsapp(phone, caption, pdf_bytes, filename)

        # Envia por E-mail
        html_body = (
            f"<p>Olá {first},</p>"
            f"<p>Segue em anexo o PDF do pacote <strong>{pacote}</strong>.</p>"
        )
        send_email(email, "Seu arquivo solicitado", html_body, pdf_bytes, filename)

        return JSONResponse({"status": "sucesso"})

    except Exception as e:
        import traceback
        traceback.print_exc()  # Mostra erro nos logs Render
        raise HTTPException(
            status_code=500,
            detail=str(e)
        ) from e

@app.get("/health")
def health():
    return {"ok": True}
