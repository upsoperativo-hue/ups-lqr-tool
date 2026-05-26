import streamlit as st
import re
from datetime import datetime
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.colors import white, black
from reportlab.graphics.barcode import createBarcodeDrawing
from reportlab.graphics import renderPDF
from reportlab.lib.units import mm
from pypdf import PdfReader, PdfWriter

st.title("Compilatore LQR UPS — Barcode Vettoriali")

# ============================================================
# 1) UPLOAD PDF TEMPLATE
# ============================================================
uploaded_pdf = st.file_uploader("Carica il PDF LQR (es: LQR 2004.pdf)", type="pdf")

if uploaded_pdf:
    template_bytes = uploaded_pdf.read()
    template_pdf = PdfReader(BytesIO(template_bytes))

    st.success("PDF LQR caricato correttamente.")

    # ============================================================
    # 2) INPUT TARGA
    # ============================================================
    raw_targa = st.text_input("Inserisci la targa del mezzo/cassa:")
    targa = re.sub(r"[^A-Za-z0-9]", "", raw_targa).upper()

    if raw_targa and not targa:
        st.error("La targa deve contenere solo lettere e numeri.")

    # ============================================================
    # 3) INPUT TIPO
    # ============================================================
    tipo = st.selectbox("Tipo mezzo", ["", "NAVETTA", "BILICO", "CASSA"])

    prefissi = {
        "NAVETTA": "OWZ",
        "BILICO": "LP",
        "CASSA": "UPST"
    }

    # ============================================================
    # 4) HUB (solo NAVETTA)
    # ============================================================
    hub = None
    hub_code = None
    hub_num = None
    hub_letter = "T"

    if tipo == "NAVETTA":
        hub = st.selectbox("Seleziona HUB", ["", "BLQ", "BGY"])

        if hub == "BLQ":
            hub_code = "IT"
            hub_num = "4209"
        elif hub == "BGY":
            hub_code = "IT"
            hub_num = "3489"

    # ============================================================
    # 5) SC opzionale
    # ============================================================
    sc_choice = st.selectbox("Vuoi inserire un SC ufficiale UPS?", ["NO", "SI"])

    sc_value = None
    if sc_choice == "SI":
        sc_value = st.text_input("Inserisci SC (es: SC1234567890)").upper()
        if sc_value and not re.match(r"^SC\d{10}$", sc_value):
            st.error("SC NON valido. Deve essere 'SC' + 10 numeri.")
            sc_value = None

    # ============================================================
    # 6) GENERA PDF
    # ============================================================
    if st.button("Genera PDF LQR"):

        if not targa:
            st.error("Inserisci una targa valida.")
            st.stop()

        if tipo == "":
            st.error("Seleziona il tipo mezzo.")
            st.stop()

        if tipo == "NAVETTA" and hub == "":
            st.error("Seleziona l'HUB.")
            st.stop()

        # ------------------------------------------------------------
        # CREA OVERLAY
        # ------------------------------------------------------------
        overlay_buffer = BytesIO()
        c = canvas.Canvas(overlay_buffer, pagesize=letter)

        oggi = datetime.now().strftime("%d/%m")
        c.setFont("Helvetica", 10)
        c.setFillColor(black)
        c.drawString(100, 720, oggi)

        # Codici fissi
        c.drawString(142, 720, "IT")
        c.drawString(170, 720, "4138")
        c.drawString(212, 720, "L")

        # HUB dinamico
        if tipo == "NAVETTA":
            c.drawString(25, 618, hub_code)
            c.drawString(55, 618, hub_num)
            c.drawString(95, 618, hub_letter)

        elif tipo == "CASSA":
            c.drawString(25, 618, "IT")
            c.drawString(55, 618, "4219")
            c.drawString(95, 618, "T")

        elif tipo == "BILICO":
            c.drawString(25, 618, "IT")
            c.drawString(55, 618, "2009")
            c.drawString(95, 618, "N")

        # Targa
        c.drawCentredString(52, 705, targa)

        # ------------------------------------------------------------
        # FUNZIONE PER BARCODE VETTORIALE + TESTO + RETTANGOLO
        # ------------------------------------------------------------
        def draw_scaled_barcode(c, value, box_x1, box_y1, box_x2, box_y2):
            box_w = box_x2 - box_x1
            box_h = box_y2 - box_y1

            # rettangolo bianco pieno che COPRE il template
            c.setFillColor(white)
            c.rect(box_x1, box_y1, box_w, box_h, fill=1, stroke=0)

            # barcode vettoriale
            bc = createBarcodeDrawing(
                "Code128",
                value=value,
                barHeight=15 * mm,
                barWidth=0.35 * mm,
                humanReadable=False
            )

            # scala barcode per farlo stare nel box
            scale = min(
                (box_w * 0.6) / bc.width,
                (box_h * 0.6) / bc.height
            )

            # barcode più vicino al testo
            x = box_x1 + (box_w - bc.width * scale) / 2
            y = box_y1 + (box_h - bc.height * scale) / 2 + 4

            c.saveState()
            c.translate(x, y)
            c.scale(scale, scale)
            renderPDF.draw(bc, c, 0, 0)
            c.restoreState()

            # testo più vicino al barcode
            c.setFillColor(black)
            c.setFont("Helvetica", 8)
            c.drawCentredString(box_x1 + box_w / 2, box_y1 + 6, value)

        # ------------------------------------------------------------
        # BARCODE TARGA
        # ------------------------------------------------------------
        prefisso = prefissi[tipo]
        barcode_value = f"{prefisso}{targa}E"

        draw_scaled_barcode(c, barcode_value, 20, 118, 248, 240)

        # ------------------------------------------------------------
        # BARCODE SC (se presente)
        # ------------------------------------------------------------
        if sc_value:
            draw_scaled_barcode(c, sc_value, 415, 160, 570, 240)

        c.save()
        overlay_buffer.seek(0)

        # ------------------------------------------------------------
        # MERGE PDF
        # ------------------------------------------------------------
        overlay_pdf = PdfReader(overlay_buffer)
        writer = PdfWriter()

        page = template_pdf.pages[0]
        page.merge_page(overlay_pdf.pages[0])
        writer.add_page(page)

        output_buffer = BytesIO()
        writer.write(output_buffer)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"LQR_compilato_{targa}_{timestamp}.pdf"

        st.success("PDF generato correttamente.")

        st.download_button(
            "Scarica PDF",
            data=output_buffer.getvalue(),
            file_name=filename,
            mime="application/pdf"
        )
