import os
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from PIL import Image

# 1. Pengaturan Halaman Dashboard Streamlit
st.set_page_config(
    page_title="Monitoring Beban SLD Purwodadi-11",
    page_icon="⚡",
    layout="wide"
)

# 2. Fungsi Koneksi & Ambil Data dari Google Sheets (Support Lokal & Cloud Secrets)
@st.cache_data(ttl=60)  # Cache data selama 60 detik
def load_data_from_sheet():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    # Cek apakah running di Streamlit Cloud (st.secrets) atau Lokal (credentials.json)
    if "gcp_service_account" in st.secrets:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    else:
        creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
        
    client = gspread.authorize(creds)
    sheet = client.open("Database_Beban_Purwodadi11").sheet1
    
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    # Bersihkan nama kolom dari spasi berlebih
    df.columns = df.columns.str.strip()
    return df

# 3. Header Utama Dashboard
st.title("⚡ Monitoring Real-Time Beban SLD Purwodadi-11")
st.markdown("Sistem pemantauan arus beban (Phasa R, S, T) pada PMT, Recloser, dan LBS berbasis Google Sheets.")

# Tombol Refresh Data
if st.button("🔄 Perbarui Data (Refresh)"):
    st.cache_data.clear()
    st.success("Data berhasil diperbarui dari Google Sheets!")

# 4. Memuat Data & Menjalankan Logika Filter Waktu
try:
    df_raw = load_data_from_sheet()
    
    if not df_raw.empty:
        # Menentukan Kolom Waktu / Timestamp
        kolom_waktu = None
        for col in ['Timestamp_Device_ID', 'Timestamp Device_ID', 'Timestamp']:
            if col in df_raw.columns:
                kolom_waktu = col
                break

        # Filter Waktu (Dropdown Jam)
        if kolom_waktu:
            st.subheader("⏱️ Pilih Jam Pemantauan Beban")
            daftar_jam = df_raw[kolom_waktu].unique()
            pilih_jam = st.selectbox("Pilih Sesi Waktu Pengukuran:", daftar_jam, index=0)
            
            # Filter DataFrame berdasarkan jam yang dipilih
            df_beban = df_raw[df_raw[kolom_waktu] == pilih_jam].copy()
        else:
            pilih_jam = "Semua Sesi (Kolom Timestamp tidak ditemukan)"
            df_beban = df_raw.copy()

        # A. Ringkasan Perangkat
        st.subheader("📊 Ringkasan Perangkat Terdaftar")
        st.metric(label=f"Total Perangkat Terpantau (Sesi {pilih_jam})", value=len(df_beban))
        
        # B. Tabel Log Beban Per Sesi Jam
        st.subheader(f"📋 Tabel Log Beban Perangkat - Sesi {pilih_jam}")
        st.dataframe(df_beban, use_container_width=True)
        
        # C. Grafik Perbandingan Arus Phasa (R, S, T) Per Sesi Jam
        st.subheader(f"📈 Grafik Perbandingan Arus Phasa (R, S, T) - Sesi {pilih_jam}")
        if 'Nama_Perangkat' in df_beban.columns:
            chart_data = df_beban.set_index("Nama_Perangkat")[["Ampere_R", "Ampere_S", "Ampere_T"]]
            st.bar_chart(chart_data)

        # D. Visualisasi Gambar SLD
        st.subheader("🗺️ Visualisasi Single Line Diagram Purwodadi-11")
        gambar_ditemukan = None
        for ekstensi in ["sld_purwodadi11.jpg", "sld_purwodadi11.jpeg", "sld_purwodadi11.png", "SLD PWI11.png"]:
            if os.path.exists(ekstensi):
                gambar_ditemukan = ekstensi
                break

        if gambar_ditemukan:
            image_sld = Image.open(gambar_ditemukan)
            st.image(image_sld, caption=f"SLD Purwodadi-11 Real-Time Monitoring ({gambar_ditemukan})", use_container_width=True)
        else:
            st.warning("⚠️ File gambar SLD belum ditemukan di folder repository. Pastikan nama file gambar Anda sudah sesuai.")

        # E. Detail Arus Perangkat Dalam Bentuk Metrik Card
        st.subheader(f"⚡ Detail Arus Perangkat pada Sesi: {pilih_jam}")
        for index, row in df_beban.iterrows():
            nama_dev = row.get('Nama_Perangkat', 'Unknown')
            r = row.get('Ampere_R', 0)
            s = row.get('Ampere_S', 0)
            t = row.get('Ampere_T', 0)
            stat = row.get('Status', 'CLOSE')
            
            col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 2])
            with col1:
                st.markdown(f"**📌 {nama_dev}**")
            with col2:
                st.metric("Phasa R", f"{r} A")
            with col3:
                st.metric("Phasa S", f"{s} A")
            with col4:
                st.metric("Phasa T", f"{t} A")
            with col5:
                st.markdown(f"Status: `{stat}`")
            st.divider()

    else:
        st.warning("⚠️ Data di Google Sheets masih kosong.")

except Exception as e:
    st.error(f"Gagal memuat data dari Google Sheets. Detail Error: {e}")
