# app.py (optimized version — uses fpdf for lightweight PDF generation)
import io, os, json, zipfile
from datetime import datetime
import pandas as pd
import streamlit as st
from fpdf import FPDF

# ---------- Files & defaults ----------
DATA_PATH = "students_sample.csv"
CONFIG_PATH = "config.json"
RECEIPTS_DIR = "receipts"

DEFAULT_CONFIG = {
    "app_title": "Sistem Yuran Asrama (Mengaji & Silat)",
    "branding_text": "SMK PONDOK UPEH",
    "currency": "RM",
    "receipt_footer": "Resit ini dijana secara digital dan tidak memerlukan tandatangan.",
    "ui_labels": {"mengaji": "Yuran Mengaji", "silat": "Yuran Silat"}
}

REQUIRED_COLS = [
    "NAMA","NO_KP","TINGKATAN","KELAS",
    "MENGAJI_STATUS","MENGAJI_AMOUNT","MENGAJI_DATE",
    "SILAT_STATUS","SILAT_AMOUNT","SILAT_DATE"
]

# ---------- Helpers ----------
def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return DEFAULT_CONFIG.copy()

def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    for c in REQUIRED_COLS:
        if c not in df.columns:
            df[c] = ""
    df["MENGAJI_AMOUNT"] = pd.to_numeric(df["MENGAJI_AMOUNT"], errors="coerce").fillna(0.0)
    df["SILAT_AMOUNT"] = pd.to_numeric(df["SILAT_AMOUNT"], errors="coerce").fillna(0.0)
    return df[REQUIRED_COLS]

def load_students():
    if os.path.exists(DATA_PATH):
        df = pd.read_csv(DATA_PATH, dtype=str, keep_default_na=False)
        for col in ["MENGAJI_AMOUNT","SILAT_AMOUNT"]:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        return ensure_columns(df)
    return ensure_columns(pd.DataFrame(columns=REQUIRED_COLS))

def save_students(df: pd.DataFrame):
    df.to_csv(DATA_PATH, index=False)

def next_receipt_no(prefix="DN"):
    return f"{prefix}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

# ---------- PDF generation (FPDF) ----------
def build_receipt_pdf_bytes(cfg, student, fee_type_label, amount, date_str, receipt_no):
    pdf = FPDF(format="A4")
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 8, cfg.get("branding_text", DEFAULT_CONFIG["branding_text"]), ln=True)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 6, "RESIT PEMBAYARAN YURAN", ln=True)
    pdf.ln(4)

    # Student info
    pdf.set_font("Arial", "", 11)
    pdf.cell(40, 6, "Nama:", ln=False)
    pdf.cell(0, 6, student["NAMA"], ln=True)
    pdf.cell(40, 6, "No. KP:", ln=False)
    pdf.cell(0, 6, student["NO_KP"], ln=True)
    pdf.cell(40, 6, "Tingkatan / Kelas:", ln=False)
    pdf.cell(0, 6, f"{student['TINGKATAN']} / {student['KELAS']}", ln=True)
    pdf.ln(4)

    # Payment section
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 7, "Yuran Dibayar:", ln=True)
    pdf.set_font("Arial", "", 11)
    pdf.cell(70, 6, f"- {fee_type_label}", ln=False)
    pdf.cell(0, 6, f"{cfg.get('currency','RM')}{amount:,.2f}", ln=True)
    pdf.ln(6)

    # Metadata
    pdf.cell(40, 6, "Tarikh:", ln=False)
    pdf.cell(0, 6, date_str, ln=True)
    pdf.cell(40, 6, "No. Resit:", ln=False)
    pdf.cell(0, 6, receipt_no, ln=True)
    pdf.ln(8)

    pdf.set_font("Arial", "I", 9)
    pdf.multi_cell(0, 5, cfg.get("receipt_footer", DEFAULT_CONFIG["receipt_footer"]))

    # return bytes (fpdf returns str for 'S' in some versions; ensure bytes)
    out = pdf.output(dest="S")
    if isinstance(out, str):
        out = out.encode("latin-1")
    return out

def generate_single_pdf(cfg, student_row, fee_key):
    fee_map = {"MENGAJI": ("MENGAJI_AMOUNT", "MENGAJI_DATE"),
               "SILAT": ("SILAT_AMOUNT", "SILAT_DATE")}
    label = cfg["ui_labels"]["mengaji"] if fee_key=="MENGAJI" else cfg["ui_labels"]["silat"]
    amt_col, date_col = fee_map[fee_key]
    amount = float(student_row[amt_col])
    date_str = student_row[date_col] if str(student_row[date_col]) else datetime.now().strftime("%Y-%m-%d")
    rno = next_receipt_no(cfg.get("receipt_prefix","DN"))
    return build_receipt_pdf_bytes(cfg, student_row.to_dict(), label, amount, date_str, rno)

def generate_bulk_one_pdf(cfg, df_subset, fee_key):
    # create one PDF with one page per student
    final = io.BytesIO()
    # We'll create a combined FPDF by aggregating pages (recreate each page)
    # Simpler: create an FPDF, add pages for each student and return bytes.
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    label = cfg["ui_labels"]["mengaji"] if fee_key=="MENGAJI" else cfg["ui_labels"]["silat"]
    for _, row in df_subset.iterrows():
        pdf.add_page()
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 8, cfg.get("branding_text", DEFAULT_CONFIG["branding_text"]), ln=True)
        pdf.set_font("Arial", "", 12)
        pdf.cell(0, 6, "RESIT PEMBAYARAN YURAN", ln=True)
        pdf.ln(4)

        pdf.set_font("Arial", "", 11)
        pdf.cell(40, 6, "Nama:", ln=False); pdf.cell(0, 6, row["NAMA"], ln=True)
        pdf.cell(40, 6, "No. KP:", ln=False); pdf.cell(0, 6, row["NO_KP"], ln=True)
        pdf.cell(40, 6, "Tingkatan / Kelas:", ln=False); pdf.cell(0, 6, f"{row['TINGKATAN']} / {row['KELAS']}", ln=True)
        pdf.ln(4)

        amt = float(row["MENGAJI_AMOUNT"] if fee_key=="MENGAJI" else row["SILAT_AMOUNT"])
        date_str = row["MENGAJI_DATE"] if fee_key=="MENGAJI" else row["SILAT_DATE"]
        date_str = date_str if str(date_str) else datetime.now().strftime("%Y-%m-%d")
        rno = next_receipt_no(cfg.get("receipt_prefix","DN"))

        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 7, "Yuran Dibayar:", ln=True)
        pdf.set_font("Arial", "", 11)
        pdf.cell(70, 6, f"- {label}", ln=False)
        pdf.cell(0, 6, f"{cfg.get('currency','RM')}{amt:,.2f}", ln=True)
        pdf.ln(6)

        pdf.cell(40, 6, "Tarikh:", ln=False); pdf.cell(0, 6, date_str, ln=True)
        pdf.cell(40, 6, "No. Resit:", ln=False); pdf.cell(0, 6, rno, ln=True)
        pdf.ln(8)
        pdf.set_font("Arial", "I", 9)
        pdf.multi_cell(0, 5, cfg.get("receipt_footer", DEFAULT_CONFIG["receipt_footer"]))

    out = pdf.output(dest="S")
    if isinstance(out, str): out = out.encode("latin-1")
    return out

# ---------- Streamlit UI ----------
st.set_page_config(page_title="Sistem Yuran (Ringkas)", layout="wide")
cfg = load_config()
st.title(cfg.get("app_title", DEFAULT_CONFIG["app_title"]))

tabs = st.tabs(["📋 Data", "🧾 Resit", "⚙️ Tetapan / Import"])
tab_data, tab_receipt, tab_settings = tabs

with tab_data:
    st.subheader("Senarai & Sunting Pelajar (Tambah / Padam / Edit)")
    df = load_students()

    # Add student
    with st.expander("➕ Tambah Pelajar Baharu"):
        with st.form("add_student"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Nama")
            ic = c2.text_input("No. KP")
            c3, c4 = st.columns(2)
            ting = c3.selectbox("Tingkatan", ["4","5"])
            kelas = c4.selectbox("Kelas", ["Inovatif","Bestari","Dinamik","Kreatif"])
            mengaji_amt = st.number_input("Amaun Yuran Mengaji (RM)", min_value=0.0, step=1.0, value=0.0)
            silat_amt = st.number_input("Amaun Yuran Silat (RM)", min_value=0.0, step=1.0, value=0.0)
            submitted = st.form_submit_button("Tambah")
        if submitted:
            new = {
                "NAMA": name, "NO_KP": ic, "TINGKATAN": ting, "KELAS": kelas,
                "MENGAJI_STATUS": "Belum Bayar","MENGAJI_AMOUNT": float(mengaji_amt),"MENGAJI_DATE": "",
                "SILAT_STATUS": "Belum Bayar","SILAT_AMOUNT": float(silat_amt),"SILAT_DATE": ""
            }
            df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
            save_students(ensure_columns(df))
            st.success("Pelajar ditambah.")

    st.caption("Edit terus dalam jadual. Klik 'Simpan Perubahan' selepas selesai.")
    edited = st.data_editor(df, use_container_width=True, num_rows="dynamic",
                            column_config={
                                "MENGAJI_STATUS": st.column_config.SelectboxColumn("MENGAJI_STATUS", options=["Belum Bayar","Sudah Bayar"]),
                                "SILAT_STATUS": st.column_config.SelectboxColumn("SILAT_STATUS", options=["Belum Bayar","Sudah Bayar"]),
                            })
    if st.button("💾 Simpan Perubahan"):
        save_students(ensure_columns(edited))
        st.success("Disimpan.")

    with st.expander("🗑️ Padam Pelajar"):
        to_delete = st.multiselect("Pilih baris untuk dipadam", options=list(range(len(edited))),
                                   format_func=lambda i: f"{edited.loc[i,'NAMA']} • {edited.loc[i,'NO_KP']}")
        if st.button("Padam Dipilih"):
            if to_delete:
                newdf = edited.drop(index=to_delete).reset_index(drop=True)
                save_students(ensure_columns(newdf))
                st.success(f"{len(to_delete)} rekod dipadam.")
            else:
                st.warning("Tiada pilihan dipadam.")

with tab_receipt:
    st.subheader("Jana Resit (Individu / Bulk)")
    os.makedirs(RECEIPTS_DIR, exist_ok=True)
    df = load_students()
    if df.empty:
        st.info("Tiada data. Import CSV atau tambah pelajar.")
    else:
        q = st.text_input("Cari Nama / No. KP / Tingkatan / Kelas")
        filtered = df.copy()
        if q:
            s = q.lower()
            mask = (df["NAMA"].str.lower().str.contains(s, na=False) |
                    df["NO_KP"].str.lower().str.contains(s, na=False) |
                    df["TINGKATAN"].astype(str).str.contains(s, na=False) |
                    df["KELAS"].str.lower().str.contains(s, na=False))
            filtered = df[mask].reset_index(drop=True)

        col1, col2 = st.columns(2)
        fee_label_choice = col1.selectbox("Jenis Yuran", [cfg["ui_labels"]["mengaji"], cfg["ui_labels"]["silat"]])
        fee_key = "MENGAJI" if fee_label_choice == cfg["ui_labels"]["mengaji"] else "SILAT"
        only_paid = col2.checkbox("Hanya yang Sudah Bayar", value=False)
        status_col = "MENGAJI_STATUS" if fee_key=="MENGAJI" else "SILAT_STATUS"
        list_df = filtered[filtered[status_col]=="Sudah Bayar"] if only_paid else filtered

        st.write(f"{len(list_df)} rekod ditemui.")
        selected = st.multiselect("Pilih pelajar:", options=list_df.index.tolist(),
                                  format_func=lambda i: f"{list_df.loc[i,'NAMA']} • {list_df.loc[i,'NO_KP']}")

        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("🧾 Jana Individu"):
                if not selected:
                    st.warning("Pilih seorang pelajar.")
                else:
                    row = list_df.loc[selected[0]]
                    pdf_bytes = generate_single_pdf(cfg, row, fee_key)
                    fname = f"resit_{fee_key.lower()}_{row['NAMA'].replace(' ','_')}.pdf"
                    with open(os.path.join(RECEIPTS_DIR, fname), "wb") as f:
                        f.write(pdf_bytes)
                    st.download_button("Muat Turun PDF", data=pdf_bytes, file_name=fname, mime="application/pdf")
                    st.info("Muat turun dan gunakan Share → Print (iPad).")

        with c2:
            if st.button("📄 Jana Bulk (Satu Fail PDF)"):
                if not selected:
                    st.warning("Pilih sekurang-kurangnya seorang.")
                else:
                    subset = list_df.loc[selected]
                    pdf_bytes = generate_bulk_one_pdf(cfg, subset, fee_key)
                    fname = f"bulk_{fee_key.lower()}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
                    with open(os.path.join(RECEIPTS_DIR, fname), "wb") as f:
                        f.write(pdf_bytes)
                    st.download_button("Muat Turun PDF (Semua)", data=pdf_bytes, file_name=fname, mime="application/pdf")
                    st.info("Setiap pelajar pada halaman berasingan dalam fail ini.")

        with c3:
            if st.button("🧾📦 Jana Bulk (Fail Terpisah → ZIP)"):
                if not selected:
                    st.warning("Pilih sekurang-kurangnya seorang.")
                else:
                    subset = list_df.loc[selected]
                    mem = io.BytesIO()
                    with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
                        for _, row in subset.iterrows():
                            pdfb = generate_single_pdf(cfg, row, fee_key)
                            fname = f"resit_{fee_key.lower()}_{row['NAMA'].replace(' ','_')}.pdf"
                            zf.writestr(fname, pdfb)
                            with open(os.path.join(RECEIPTS_DIR, fname), "wb") as f:
                                f.write(pdfb)
                    mem.seek(0)
                    zipname = f"resit_zip_{fee_key.lower()}_{datetime.now().strftime('%Y%m%d_%H%M')}.zip"
                    st.download_button("Muat Turun ZIP", data=mem.getvalue(), file_name=zipname, mime="application/zip")
                    st.info("Semua resit disimpan dalam folder 'receipts' juga.")

with tab_settings:
    st.subheader("Tetapan & Import/Export")
    cfg = load_config()
    cfg["app_title"] = st.text_input("Tajuk Aplikasi", value=cfg.get("app_title", DEFAULT_CONFIG["app_title"]))
    cfg["branding_text"] = st.text_input("Teks Sekolah (atas resit)", value=cfg.get("branding_text", DEFAULT_CONFIG["branding_text"]))
    cfg["currency"] = st.text_input("Mata Wang", value=cfg.get("currency","RM"))
    cfg["receipt_footer"] = st.text_input("Footer Resit", value=cfg.get("receipt_footer", DEFAULT_CONFIG["receipt_footer"]))
    cfg["ui_labels"]["mengaji"] = st.text_input("Label Yuran Mengaji", value=cfg["ui_labels"].get("mengaji","Yuran Mengaji"))
    cfg["ui_labels"]["silat"] = st.text_input("Label Yuran Silat", value=cfg["ui_labels"].get("silat","Yuran Silat"))
    if st.button("💾 Simpan Tetapan"):
        save_config(cfg)
        st.success("Tetapan disimpan.")

    st.markdown("---")
    st.write("**Import CSV (gantikan)**")
    up = st.file_uploader("Muat Naik CSV (format seperti students_sample.csv)", type=["csv"])
    if up:
        df_new = pd.read_csv(up, dtype=str, keep_default_na=False)
        save_students(ensure_columns(df_new))
        st.success("Data dimuat naik.")
    st.write("**Muat Turun Data Semasa**")
    df_now = load_students()
    st.download_button("Muat Turun CSV", data=df_now.to_csv(index=False).encode("utf-8"),
                       file_name=f"students_export_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")
