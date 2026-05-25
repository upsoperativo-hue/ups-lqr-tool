import streamlit as st
import re
from datetime import datetime
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.graphics.barcode import code128
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF
from reportlab.lib.colors import white, black
from pypdf import PdfReader, PdfWriter

st.title("Compilatore LQR UPS")

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
        # BARCODE TARGA (PATCHATO)
        # ------------------------------------------------------------
        prefisso = prefissi[tipo]
        barcode_value = f"{prefisso}{targa}E"

        X1, Y1 = 20, 118
        X2, Y2 = 248, 240
        target_width = X2 - X1
        target_height = Y2 - Y1

        c.setFillColor(white)
        c.rect(X1, Y1, target_width, target_height, fill=1, stroke=0)

        barcode = code128.Code128(
            barcode_value,
            barHeight=target_height,
            barWidth=1
        )

        scale = min(target_width / barcode.width, target_height / barcode.height) * 0.75

        x_bar = X1 + (target_width - barcode.width * scale) / 2
        y_bar = Y1 + (target_height - barcode.height * scale) / 2 + 10

        drawing = Drawing(barcode.width, barcode.height)
        drawing.add(barcode)

        renderPDF.draw(drawing, c, x_bar, y_bar)

        c.drawCentredString(X1 + target_width / 2, y_bar - 15, barcode_value)

        # ------------------------------------------------------------
        # SC opzionale (PATCHATO)
        # ------------------------------------------------------------
        if sc_value:
            SC_X1, SC_Y1 = 415, 160
            SC_X2, SC_Y2 = 570, 240
            sc_width = SC_X2 - SC_X1
            sc_height = SC_Y2 - SC_Y1

            c.setFillColor(white)
            c.rect(SC_X1, SC_Y1, sc_width, sc_height, fill=1, stroke=0)

            sc_barcode = code128.Code128(
                sc_value,
                barHeight=sc_height,
                barWidth=1
            )

            drawing_sc = Drawing(sc_barcode.width, sc_barcode.height)
            drawing_sc.add(sc_barcode)

            x_sc = SC_X1 + (sc_width - sc_barcode.width * scale) / 2
            y_sc = y_bar

            renderPDF.draw(drawing_sc, c, x_sc, y_sc)

            c.drawCentredString(SC_X1 + sc_width / 2, y_sc - 15, sc_value)

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
