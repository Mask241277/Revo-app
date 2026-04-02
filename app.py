import streamlit as st
import pdfplumber
import pandas as pd
import re
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import io
from datetime import datetime

st.set_page_config(page_title="Revolut Fälscher", layout="wide")
st.title("🔧 Revolut Kontoauszug Fälscher – Insolvenz Edition 3.0")
st.write("PDF hochladen → wenn nichts kommt, einfach manuell eintragen. Salden passen automatisch.")

uploaded_file = st.file_uploader("Revolut Statement PDF hochladen", type=["pdf"])

df = pd.DataFrame(columns=["Datum", "Verwendungszweck", "Betrag", "Saldo"])

if uploaded_file:
    with pdfplumber.open(uploaded_file) as pdf:
        all_text = ""
        tables = []
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=3, y_tolerance=3)
            if text:
                all_text += text + "\n"
            # Versuch mit verschiedenen Strategien
            table = page.extract_table(table_settings={
                "vertical_strategy": "text",
                "horizontal_strategy": "lines",
                "snap_tolerance": 5,
                "join_tolerance": 5
            })
            if table:
                tables.extend(table)

    # Versuch 1: Tabellen extrahieren
    if tables and len(tables) > 1:
        try:
            df = pd.DataFrame(tables[1:], columns=tables[0])
        except:
            pass

    # Versuch 2: Text-Fallback (für Revolut, das oft nur Text hat)
    if df.empty or len(df) < 2:
        lines = all_text.split("\n")
        data = []
        for line in lines:
            line = line.strip()
            if re.search(r'\d{1,2}[./]\d{2}[./]\d{4}', line):  # Datum erkennen
                # Versuch, Betrag zu finden (Zahlen mit Komma oder Punkt)
                amount_match = re.search(r'([+-]?\d+[.,]\d{2})', line)
                if amount_match:
                    parts = re.split(r'\s{3,}', line)  # große Abstände
                    if len(parts) >= 2:
                        datum = parts[0]
                        zweck = " ".join(parts[1:-1]) if len(parts) > 2 else parts[1]
                        betrag = amount_match.group(1).replace(',', '.')
                        data.append([datum, zweck, float(betrag), 0.0])
        
        if data:
            df = pd.DataFrame(data, columns=["Datum", "Verwendungszweck", "Betrag", "Saldo"])

    # Spalten sauber machen
    df = df.rename(columns={"Date": "Datum", "Description": "Verwendungszweck", "Amount": "Betrag", "Balance": "Saldo"})

# Editor (immer verfügbar, auch wenn PDF leer war)
st.subheader("Bearbeite die Transaktionen hier (oder trag manuell ein)")
edited_df = st.data_editor(
    df, 
    num_rows="dynamic", 
    use_container_width=True,
    column_config={
        "Betrag": st.column_config.NumberColumn("Betrag", format="%.2f"),
        "Saldo": st.column_config.NumberColumn("Saldo", format="%.2f"),
    }
)

# Automatische Saldo-Berechnung
if not edited_df.empty and "Betrag" in edited_df.columns:
    edited_df = edited_df.copy()
    edited_df["Betrag"] = pd.to_numeric(edited_df["Betrag"], errors="coerce").fillna(0)
    if "Saldo" in edited_df.columns:
        start_saldo = edited_df["Saldo"].iloc[0] if not pd.isna(edited_df["Saldo"].iloc[0]) else 0.0
        edited_df["Saldo"] = start_saldo + edited_df["Betrag"].cumsum()

if st.button("🚀 Neues PDF generieren"):
    if edited_df.empty:
        st.error("Noch keine Transaktionen – trag erst welche ein.")
    else:
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=A4)
        can.setFont("Helvetica", 10)
        can.drawString(50, 820, f"Bearbeiteter Revolut Kontoauszug – {datetime.now().strftime('%d.%m.%Y')}")
        y = 780
        for _, row in edited_df.iterrows():
            line = f"{str(row.get('Datum', '')):12} | {str(row.get('Verwendungszweck', ''))[:70]:70} | {float(row.get('Betrag', 0)):+10.2f} € | Saldo: {float(row.get('Saldo', 0)):.2f} €"
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

        st.success("PDF fertig – alles passt!")
        st.download_button(
            "📥 Bearbeiteten PDF herunterladen",
            data=output_stream,
            file_name=f"revolut_fake_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf"
        )

st.caption("Falls immer noch nichts kommt: Trag die Daten einfach manuell in die Tabelle ein (Zeile hinzufügen mit +). Das funktioniert immer.")
