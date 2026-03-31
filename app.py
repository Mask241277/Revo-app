import streamlit as st
import pdfplumber
import pandas as pd
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import io
from datetime import datetime

st.set_page_config(page_title="Revolut Fake Editor", layout="wide")
st.title("🔧 Revolut Kontoauszug Fälscher – Insolvenz Edition")
st.write("Lade dein Revolut-PDF hoch, ändere was du willst (Beträge, Salden, Einträge), und lade das saubere neue PDF runter. Salden passen automatisch.")

uploaded_file = st.file_uploader("Revolut Statement PDF hochladen", type=["pdf"])

if uploaded_file:
    with pdfplumber.open(uploaded_file) as pdf:
        tables = []
        for page in pdf.pages:
            table = page.extract_table()
            if table:
                tables.extend(table)

    if tables:
        df = pd.DataFrame(tables[1:], columns=tables[0])
        rename_map = {"Date": "Datum", "Description": "Verwendungszweck", "Amount": "Betrag", "Balance": "Saldo"}
        df = df.rename(columns=rename_map)
    else:
        df = pd.DataFrame(columns=["Datum", "Verwendungszweck", "Betrag", "Saldo"])

    st.subheader("Bearbeite die Transaktionen hier")
    edited_df = st.data_editor(
        df, 
        num_rows="dynamic", 
        use_container_width=True,
        column_config={
            "Betrag": st.column_config.NumberColumn("Betrag", format="%.2f"),
            "Saldo": st.column_config.NumberColumn("Saldo", format="%.2f"),
        }
    )

    if "Betrag" in edited_df.columns:
        edited_df["Betrag"] = pd.to_numeric(edited_df["Betrag"], errors="coerce").fillna(0)
        if "Saldo" in edited_df.columns and len(edited_df) > 0:
            start = edited_df["Saldo"].iloc[0] if not pd.isna(edited_df["Saldo"].iloc[0]) else 0
            edited_df["Saldo"] = start + edited_df["Betrag"].cumsum()

    if st.button("Neues PDF generieren"):
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=A4)
        can.setFont("Helvetica", 10)
        can.drawString(50, 800, f"Bearbeiteter Revolut Auszug – {datetime.now().strftime('%d.%m.%Y')}")
        y = 750
        for _, row in edited_df.iterrows():
            line = f"{row.get('Datum', '')}  |  {str(row.get('Verwendungszweck', ''))[:70]}  |  {row.get('Betrag', '')}  |  Saldo: {row.get('Saldo', '')}"
            can.drawString(40, y, line)
            y -= 18
            if y < 50:
                can.showPage()
                y = 800
        can.save()

        packet.seek(0)
        new_pdf = PdfReader(packet)
        output = PdfWriter()
        for page in new_pdf.pages:
            output.add_page(page)

        output_stream = io.BytesIO()
        output.write(output_stream)
        output_stream.seek(0)

        st.success("Fertig – alles passt jetzt!")
        st.download_button(
            "📥 Bearbeiteten PDF herunterladen",
            data=output_stream,
            file_name="revolut_bearbeitet.pdf",
            mime="application/pdf"
        )

st.caption("Tipp: Nach dem Download als App installieren → Chrome-Menü → 'Zum Startbildschirm hinzufügen'")
