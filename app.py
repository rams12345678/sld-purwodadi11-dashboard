
from pathlib import Path
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(
    page_title="Monitoring Beban SLD Purwodadi-11",
    page_icon="⚡",
    layout="wide"
)

BASE = Path(__file__).resolve().parent

SPREADSHEET_ID = "1oaerHtNXS-QPNsJzAEd5Ljl54H4pgt32YqfnF-fMiTQ"
WORKSHEET_NAME = "Realtime_Beban"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly"
]


@st.cache_data(ttl=60, show_spinner="Mengambil data dari Google Sheets...")
def load_data():
    if "gcp_service_account" in st.secrets:
        info = dict(st.secrets["gcp_service_account"])
        info["private_key"] = info["private_key"].replace("\\n", "\n")

        credentials = Credentials.from_service_account_info(
            info,
            scopes=SCOPES
        )

    elif (BASE / "credentials.json").exists():
        credentials = Credentials.from_service_account_file(
            str(BASE / "credentials.json"),
            scopes=SCOPES
        )
    else:
        raise RuntimeError(
            "Konfigurasi [gcp_service_account] belum tersedia di Streamlit Secrets."
        )

    client = gspread.authorize(credentials)
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    worksheet = spreadsheet.worksheet(WORKSHEET_NAME)

    rows = worksheet.get_all_records()
    df = pd.DataFrame(rows)

    if not df.empty:
        df.columns = df.columns.astype(str).str.strip()

    return df


st.title("⚡ Monitoring Real-Time Beban SLD Purwodadi-11")
st.caption(
    "Pemantauan arus phasa R, S, T pada PMT, Recloser, dan LBS dari Google Sheets."
)

if st.button("🔄 Perbarui Data"):
    load_data.clear()
    st.rerun()

try:
    df = load_data()
except Exception as exc:
    st.error("Koneksi Google Sheets belum berhasil.")
    st.code(f"{type(exc).__name__}: {exc}")
    st.info(
        "Periksa akses Viewer untuk Service Account, "
        "Google Sheets API, dan konfigurasi Secrets."
    )
    st.stop()

if df.empty:
    st.warning("Google Sheets berhasil dibaca, tetapi belum ada data.")
    st.stop()

time_col = next(
    (
        c for c in (
            "Timestamp Device_ID",
            "Timestamp_Device_ID",
            "Timestamp"
        )
        if c in df.columns
    ),
    None
)

if time_col:
    sessions = df[time_col].dropna().astype(str).unique().tolist()
    sessions = sorted(sessions, reverse=True)

    session = st.selectbox(
        "⏱️ Pilih sesi waktu pengukuran",
        sessions
    ) if sessions else "Semua sesi"

    data = (
        df[df[time_col].astype(str) == session].copy()
        if sessions else df.copy()
    )
else:
    session = "Semua sesi"
    data = df.copy()

st.metric(
    f"Total perangkat terpantau — {session}",
    len(data)
)

st.subheader("📋 Data beban perangkat")
st.dataframe(
    data,
    use_container_width=True,
    hide_index=True
)

required = [
    "Nama_Perangkat",
    "Ampere_R",
    "Ampere_S",
    "Ampere_T"
]

missing = [c for c in required if c not in data.columns]

if not missing:
    chart = data[required].copy()

    for col in required[1:]:
        chart[col] = pd.to_numeric(
            chart[col].astype(str).str.replace(
                ",", ".", regex=False
            ),
            errors="coerce"
        )

    st.subheader("📈 Grafik perbandingan arus phasa")
    st.bar_chart(
        chart.set_index("Nama_Perangkat")[required[1:]]
    )
else:
    st.warning(
        "Kolom grafik belum lengkap: " + ", ".join(missing)
    )

st.subheader("🗺️ Single Line Diagram Purwodadi-11")

img = next(
    (
        BASE / name
        for name in (
            "sld_purwodadi11.jpg",
            "sld_purwodadi11.jpeg",
            "sld_purwodadi11.png"
        )
        if (BASE / name).exists()
    ),
    None
)

if img:
    st.image(
        str(img),
        caption="SLD Purwodadi-11",
        use_container_width=True
    )
else:
    st.warning(
        "File gambar SLD belum ditemukan di repository."
    )

st.subheader("⚡ Detail arus perangkat")

for _, row in data.iterrows():
    cols = st.columns(5)

    cols[0].markdown(
        f"**{row.get('Nama_Perangkat', 'Tidak diketahui')}**"
    )

    for i, phase in enumerate(("R", "S", "T"), start=1):
        cols[i].metric(
            f"Phasa {phase}",
            f"{row.get('Ampere_' + phase, '-')} A"
        )

    cols[4].write(
        f"Status: {row.get('Status', '-')}"
    )

    st.divider()
