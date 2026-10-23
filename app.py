from pathlib import Path
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title='Monitoring Beban SLD Purwodadi-11', page_icon='⚡', layout='wide')
BASE = Path(__file__).resolve().parent
scope = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly"
]

@st.cache_data(ttl=60, show_spinner='Mengambil data Google Sheets...')
def load_data():
    if 'gcp_service_account' in st.secrets:
        info = dict(st.secrets['gcp_service_account'])
        info['private_key'] = info['private_key'].replace('\\n', '\n')
        credentials = Credentials.from_service_account_info(info, scopes=SCOPES)
    elif (BASE / 'credentials.json').exists():
        credentials = Credentials.from_service_account_file(str(BASE / 'credentials.json'), scopes=SCOPES)
    else:
        raise RuntimeError('Secrets [gcp_service_account] belum diatur. Tambahkan di Streamlit Cloud > App settings > Secrets.')
    client = gspread.authorize(credentials)
    sheet_id = st.secrets.get('sheet_id', '')
    sheet = client.open_by_key(sheet_id).sheet1 if sheet_id else client.open('Database_Beban_Purwodadi11').sheet1
    rows = sheet.get_all_records()
    frame = pd.DataFrame(rows)
    frame.columns = frame.columns.str.strip()
    return frame

st.title('⚡ Monitoring Real-Time Beban SLD Purwodadi-11')
st.caption('Pemantauan arus phasa R, S, T pada PMT, Recloser, dan LBS dari Google Sheets.')
if st.button('🔄 Perbarui Data'):
    load_data.clear()
    st.rerun()

try:
    df = load_data()
except Exception as exc:
    st.error('Koneksi Google Sheets belum berhasil.')
    st.code(f'{type(exc).__name__}: {exc}')
    st.info('Periksa format Secrets, akses Share Google Sheets, Google Sheets API, serta nama atau ID spreadsheet.')
    st.stop()

if df.empty:
    st.warning('Google Sheets berhasil dibaca, tetapi belum ada baris data.')
    st.stop()

time_col = next((c for c in ('Timestamp_Device_ID', 'Timestamp Device_ID', 'Timestamp') if c in df.columns), None)
if time_col:
    sessions = df[time_col].dropna().astype(str).unique().tolist()
    session = st.selectbox('⏱️ Pilih sesi waktu pengukuran', sessions) if sessions else 'Semua sesi'
    data = df[df[time_col].astype(str).eq(session)].copy() if sessions else df.copy()
else:
    session = 'Semua sesi'
    data = df.copy()

st.metric(f'Total perangkat terpantau — {session}', len(data))
st.subheader('📋 Data beban perangkat')
st.dataframe(data, use_container_width=True)
required = ['Nama_Perangkat', 'Ampere_R', 'Ampere_S', 'Ampere_T']
missing = [c for c in required if c not in data.columns]
if not missing:
    chart = data[required].copy()
    for c in required[1:]:
        chart[c] = pd.to_numeric(chart[c].astype(str).str.replace(',', '.', regex=False), errors='coerce')
    st.subheader('📈 Grafik arus per phasa')
    st.bar_chart(chart.set_index('Nama_Perangkat')[required[1:]])
else:
    st.warning('Kolom grafik belum lengkap: ' + ', '.join(missing))

st.subheader('🗺️ Single Line Diagram Purwodadi-11')
img = next((BASE / name for name in ('sld_purwodadi11.jpg', 'sld_purwodadi11.jpeg', 'sld_purwodadi11.png') if (BASE / name).exists()), None)
if img:
    st.image(str(img), caption='SLD Purwodadi-11', use_container_width=True)
else:
    st.warning('File gambar SLD tidak ditemukan.')

st.subheader('⚡ Detail arus perangkat')
for _, row in data.iterrows():
    cols = st.columns(5)
    cols[0].markdown(f"**{row.get('Nama_Perangkat', 'Tidak diketahui')}**")
    for i, phase in enumerate(('R', 'S', 'T'), start=1):
        cols[i].metric(f'Phasa {phase}', f"{row.get('Ampere_' + phase, '-')} A")
    cols[4].write(f"Status: {row.get('Status', '-')}")
    st.divider()
