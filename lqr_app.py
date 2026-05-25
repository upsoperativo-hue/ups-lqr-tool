import streamlit as st
import re
from datetime import datetime
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.colors import white, black
from reportlab.lib.utils import ImageReader
from pypdf import PdfReader, PdfWriter

import barcode
from barcode.writer import SVGWriter
import cairosvg
from PIL import Image

st.title("Compilatore LQR UPS — Barcode SVG")

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
        # FUNZIONE PER GENERARE BARCODE SVG → PNG
        # ------------------------------------------------------------
        def genera_barcode_png(value):
            svg_bytes = BytesIO()
            barcode_class = barcode.get_barcode_class("code128")
            barcode_obj = barcode_class(value, writer=SVGWriter())
            barcode_obj.write(svg_bytes)

            svg_bytes.seek(0)
            png_bytes = cairosvg.svg2png(bytestring=svg_bytes.getvalue())

            return Image.open(BytesIO(png_bytes))

        # ------------------------------------------------------------
        # BARCODE TARGA (SVG → PNG)
        # ------------------------------------------------------------
        prefisso = prefissi[tipo]
        barcode_value = f"{prefisso}{targa}E"

        barcode_img = genera_barcode_png(barcode_value)

        X1, Y1 = 20, 118
        X2, Y2 = 248, 240
        target_width = X2 - X1
        target_height = Y2 - Y1

        c.setFillColor(white)
        c.rect(X1, Y1, target_width, target_height, fill=1, stroke=0)

        barcode_img = barcode_img.resize((int(target_width), int(target_height)))
        c.drawImage(ImageReader(barcode_img), X1, Y1)

        c.drawCentredString(X1 + target_width / 2, Y1 - 15, barcode_value)

        # ------------------------------------------------------------
        # SC opzionale (SVG → PNG)
        # ------------------------------------------------------------
        if sc_value:
            SC_X1, SC_Y1 = 415, 160
            SC_X2, SC_Y2 = 570, 240
            sc_width = SC_X2 - SC_X1
            sc_height = SC_Y2 - SC_Y1

            c.setFillColor(white)
            c.rect(SC_X1, SC_Y1, sc_width, sc_height, fill=1, stroke=0)

            sc_img = genera_barcode_png(sc_value)
            sc_img = sc_img.resize((int(sc_width), int(sc_height)))

            c.drawImage(ImageReader(sc_img), SC_X1, SC_Y1)
            c.drawCentredString(SC_X1 + sc_width / 2, SC_Y1 - 15, sc_value)

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
