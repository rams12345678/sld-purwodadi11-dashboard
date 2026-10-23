"""Dashboard V2 – Monitoring Beban SLD Purwodadi-11.
Deploy app.py + requirements.txt + sld_purwodadi11.jpg; keep credentials in Streamlit Secrets.
"""
from pathlib import Path
from io import BytesIO
import base64
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from PIL import Image
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Monitoring Beban SLD PWI11 V2", page_icon="⚡", layout="wide")
BASE = Path(__file__).resolve().parent
SPREADSHEET_ID = "1oaerHtNXS-QPNsJzAEd5Ljl54H4pgt32YqfnF-fMiTQ"
WORKSHEET_NAME = "Realtime_Beban"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
PHASES = ["Ampere_R", "Ampere_S", "Ampere_T"]
# Koordinat perkiraan pada sld_purwodadi11.jpg (2048x935). Dapat dikalibrasi.
# x,y = titik label arus pada gambar, bukan posisi fisik GIS.
POINTS = {
    "PMT-PWI11": (145, 265),
    "REC-PWI11-50": (490, 245),
    "REC-K2-603-368": (1060, 235),
    "LBS-K2-380-2": (1200, 175),
    "LBS-K2-380-11D": (1250, 85),
    "LBS-K2-11D-99-1": (1450, 105),
    "LBS-K2-370-14": (1290, 675),
    "LBS-K2-603-408": (1430, 240),
    "LBS-K2-603-536": (1590, 245),
    "LBS-BL1-421": (1770, 240),
    "LBS-BL1-426-2": (1790, 640),
}

@st.cache_data(ttl=60, show_spinner="Mengambil data Google Sheets...")
def load_data():
    if "gcp_service_account" in st.secrets:
        info = dict(st.secrets["gcp_service_account"])
        info["private_key"] = info["private_key"].replace("\\n", "\n")
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    elif (BASE / "credentials.json").exists():
        creds = Credentials.from_service_account_file(str(BASE / "credentials.json"), scopes=SCOPES)
    else:
        raise RuntimeError("Isi [gcp_service_account] di Streamlit Secrets.")
    ws = gspread.authorize(creds).open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)
    return pd.DataFrame(ws.get_all_records())

def imbalance(row):
    vals = pd.to_numeric(pd.Series([row.get(p) for p in PHASES]), errors="coerce")
    if vals.isna().any() or vals.mean() <= 0:
        return float("nan")
    return round(100 * (vals - vals.mean()).abs().max() / vals.mean(), 2)

def render_sld(data, threshold):
    image_file = next((BASE / f for f in ("sld_purwodadi11.jpg", "sld_purwodadi11.png", "sld_purwodadi11.jpeg") if (BASE / f).exists()), None)
    if image_file is None:
        st.warning("Gambar sld_purwodadi11.jpg belum ada di repository.")
        return
    img = Image.open(image_file).convert("RGB")
    w, h = img.size
    buf = BytesIO()
    img.save(buf, format="PNG")
    uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    fig = go.Figure()
    fig.add_layout_image(dict(source=uri, x=0, y=0, sizex=w, sizey=h, xref="x", yref="y", sizing="stretch", layer="below"))
    indexed = data.set_index("Nama_Perangkat")
    # Label berisi arus serentak, dengan warna indikator unbalance.
    for name, (x, y) in POINTS.items():
        if name in indexed.index:
            row = indexed.loc[name]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[-1]
            values = [row[p] for p in PHASES]
            if all(pd.notna(v) for v in values):
                value_str = " / ".join(f"{v:g}" for v in values)
                text = f"<b>{name}</b><br>R/S/T: {value_str} A"
                bad = row["Unbalance_%"] > threshold
                bg = "rgba(254,226,226,0.96)" if bad else "rgba(240,253,244,0.96)"
                border = "#b91c1c" if bad else "#15803d"
            else:
                text, bg, border = f"{name}<br>Data tidak lengkap", "#f3f4f6", "#6b7280"
        else:
            text, bg, border = f"{name}<br>Tidak ada data", "#f3f4f6", "#6b7280"
        fig.add_annotation(x=x*w/2048, y=y*h/935, text=text, showarrow=False,
                           bgcolor=bg, bordercolor=border, borderwidth=1,
                           font=dict(size=10, color="#111827"), align="center", borderpad=4)
    fig.update_xaxes(range=[0,w], visible=False, fixedrange=False)
    fig.update_yaxes(range=[h,0], visible=False, fixedrange=False, scaleanchor="x", scaleratio=1)
    fig.update_layout(height=700, margin=dict(l=0,r=0,t=5,b=5),
                      paper_bgcolor="white", plot_bgcolor="white", dragmode="pan")
    st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True, "displaylogo": False})
    st.caption("Geser/zoom diagram untuk membaca label. Posisi label awal adalah perkiraan dan dapat dikalibrasi. Warna merah = unbalance melebihi batas screening; bukan diagnosis gangguan.")

st.title("⚡ Monitoring Beban SLD Purwodadi-11 | V2")
st.caption("Data Google Sheets • seluruh switching dalam satu sesi • evaluasi arus R/S/T")
if st.button("🔄 Perbarui data sekarang"):
    load_data.clear()
    st.rerun()
try:
    df = load_data()
except Exception as e:
    st.error("Koneksi Google Sheets gagal.")
    st.code(f"{type(e).__name__}: {e}")
    st.stop()

if df.empty:
    st.warning("Spreadsheet belum memiliki baris data.")
    st.stop()
df.columns = df.columns.astype(str).str.strip()
time_col = next((x for x in ("Timestamp Device_ID", "Timestamp_Device_ID", "Timestamp") if x in df.columns), None)
required = ["Nama_Perangkat", *PHASES, "Status"]
missing = [x for x in required if x not in df.columns]
if missing or not time_col:
    st.error("Kolom Google Sheets belum lengkap: " + ", ".join(missing + (["Timestamp Device_ID"] if not time_col else [])))
    st.stop()

df["Nama_Perangkat"] = df["Nama_Perangkat"].astype(str).str.strip()
df["Status"] = df["Status"].astype(str).str.strip().str.upper()
df["Waktu"] = pd.to_datetime(df[time_col].astype(str), errors="coerce")
df = df.dropna(subset=["Waktu"])
for p in PHASES:
    df[p] = pd.to_numeric(df[p].astype(str).str.replace(",", ".", regex=False), errors="coerce")
if df.empty:
    st.error("Timestamp tidak bisa dibaca sebagai tanggal/jam.")
    st.stop()
# Bila ada duplikat perangkat pada sesi yang sama, ambil baris terakhir.
df = df.drop_duplicates(subset=["Waktu", "Nama_Perangkat"], keep="last")
df["Unbalance_%"] = df.apply(imbalance, axis=1)
times = sorted(df["Waktu"].unique(), reverse=True)

c1, c2, c3 = st.columns([2, 1, 1])
with c1:
    selected_time = st.selectbox("🕒 Pilih jam pengukuran", times,
                                 format_func=lambda t: pd.Timestamp(t).strftime("%d/%m/%Y %H:%M"))
with c2:
    threshold = st.number_input("Ambang screening unbalance (%)", min_value=1.0, max_value=100.0, value=10.0, step=1.0)
with c3:
    st.write("**Sumber data**")
    st.write("Google Sheets · Realtime_Beban")

data = df[df["Waktu"] == selected_time].copy()
prev_times = [t for t in sorted(df["Waktu"].unique()) if t < selected_time]
prev_time = prev_times[-1] if prev_times else None
if prev_time is not None:
    prev = df[df["Waktu"] == prev_time].set_index("Nama_Perangkat")
    for p in PHASES:
        data["Δ" + p[-1] + " (A)"] = data.apply(
            lambda r: r[p] - prev.at[r["Nama_Perangkat"], p]
            if r["Nama_Perangkat"] in prev.index and pd.notna(r[p]) and pd.notna(prev.at[r["Nama_Perangkat"], p]) else float("nan"), axis=1)
else:
    for p in PHASES:
        data["Δ" + p[-1] + " (A)"] = float("nan")
data["Arus Maks (A)"] = data[PHASES].max(axis=1)
data["Indikator"] = data["Unbalance_%"].apply(lambda v: "PERIKSA" if pd.notna(v) and v > threshold else ("NORMAL SCREENING" if pd.notna(v) else "DATA TIDAK LENGKAP"))

pmt = data[data["Nama_Perangkat"] == "PMT-PWI11"]
metrics = st.columns(4)
metrics[0].metric("Perangkat terpantau", len(data))
metrics[1].metric("Arus maks PMT PWI11", f"{pmt.iloc[0]['Arus Maks (A)']:g} A" if not pmt.empty else "–")
metrics[2].metric("Unbalance tertinggi", f"{data['Unbalance_%'].max():.1f}%" if data["Unbalance_%"].notna().any() else "–")
metrics[3].metric("Perlu pemeriksaan", int((data["Unbalance_%"] > threshold).sum()))
if prev_time is not None:
    st.caption(f"Perubahan arus ΔR/ΔS/ΔT dibanding sesi sebelumnya: {pd.Timestamp(prev_time):%d/%m/%Y %H:%M}.")
else:
    st.caption("Belum ada sesi sebelumnya untuk menghitung perubahan arus.")

st.subheader("🗺️ SLD dengan arus seluruh switching pada jam yang sama")
render_sld(data, threshold)

st.subheader("📋 Monitoring serentak seluruh switching")
order = st.selectbox("Urutkan tabel", ["Urutan data", "Unbalance terbesar", "Arus terbesar", "Nama perangkat"])
if order == "Unbalance terbesar":
    data = data.sort_values("Unbalance_%", ascending=False)
elif order == "Arus terbesar":
    data = data.sort_values("Arus Maks (A)", ascending=False)
elif order == "Nama perangkat":
    data = data.sort_values("Nama_Perangkat")
cols = ["Nama_Perangkat", *PHASES, "Arus Maks (A)", "Unbalance_%", "ΔR (A)", "ΔS (A)", "ΔT (A)", "Status", "Indikator"]
st.dataframe(data[cols], use_container_width=True, hide_index=True)
st.download_button("⬇️ Unduh tabel sesi (CSV)", data[cols].to_csv(index=False).encode("utf-8-sig"),
                   file_name=f"beban_pwi11_{pd.Timestamp(selected_time):%Y%m%d_%H%M}.csv", mime="text/csv")

st.subheader("🎛️ Simulasi titik perangkat & analisis historis")
selected = st.selectbox("Pilih switching untuk melihat detail", sorted(df["Nama_Perangkat"].unique()))
row = data[data["Nama_Perangkat"] == selected]
if not row.empty:
    r = row.iloc[0]
    cards = st.columns(5)
    for i, p in enumerate(PHASES):
        cards[i].metric("Fasa " + p[-1], f"{r[p]:g} A" if pd.notna(r[p]) else "–",
                        delta=f"{r['Δ'+p[-1]+' (A)']:+g} A" if pd.notna(r['Δ'+p[-1]+' (A)']) else None)
    cards[3].metric("Unbalance", f"{r['Unbalance_%']:.2f}%" if pd.notna(r["Unbalance_%"]) else "–")
    cards[4].metric("Status", r["Status"])
else:
    st.info("Perangkat tidak mempunyai data pada sesi terpilih.")
history = df[df["Nama_Perangkat"] == selected].sort_values("Waktu")
if not history.empty:
    long = history.melt(id_vars=["Waktu"], value_vars=PHASES, var_name="Fasa", value_name="Arus (A)")
    fig = px.line(long, x="Waktu", y="Arus (A)", color="Fasa", markers=True,
                  title=f"Tren arus per jam — {selected}")
    st.plotly_chart(fig, use_container_width=True)

st.subheader("📊 Perbandingan ketiga fasa seluruh switching")
long_all = data.melt(id_vars=["Nama_Perangkat"], value_vars=PHASES, var_name="Fasa", value_name="Arus (A)")
fig2 = px.bar(long_all, x="Nama_Perangkat", y="Arus (A)", color="Fasa", barmode="group",
              title="Arus R/S/T tidak ditumpuk agar perbandingan fasa akurat")
fig2.update_layout(xaxis_tickangle=-45)
st.plotly_chart(fig2, use_container_width=True)

st.info("Unbalance dihitung sebagai deviasi terbesar dari rata-rata tiga arus dibagi rata-rata × 100%. Ini indikator screening, bukan diagnosis salah fasa. Verifikasi salah fasa membutuhkan referensi topologi dan identitas/urutan fasa; perbedaan arus hulu–hilir harus memperhitungkan seluruh percabangan dan status switching.")

# ===== DASHBOARD V3: EVALUASI PER SECTION & ARUS MAKSIMUM =====
# Pemetaan awal untuk kebutuhan monitoring. Validasi batas section
# dengan SLD operasional sebelum digunakan untuk analisis hulu-hilir.
SECTION_MAP = {
    "PMT-PWI11": "SECTION-01",
    "REC-PWI11-50": "SECTION-02",
    "REC-K2-603-368": "SECTION-03",
    "LBS-K2-380-2": "SECTION-03 (CABANG)",
    "LBS-K2-380-11D": "SECTION-03 (CABANG)",
    "LBS-K2-11D-99-1": "SECTION-03 (CABANG)",
    "LBS-K2-370-14": "SECTION-04 (CABANG)",
    "LBS-K2-603-408": "SECTION-04(A)",
    "LBS-K2-603-536": "SECTION-05",
    "LBS-BL1-421": "SECTION-06(A)",
    "LBS-BL1-426-2": "SECTION-06(B)",
}

st.divider()
st.header("🧭 Evaluasi Beban Per Section & Arus Maksimum")
st.caption("Arus maksimum adalah nilai tertinggi dari R/S/T pada satu switching. "
           "Nilai maksimum section adalah maksimum switching di section tersebut, bukan penjumlahan arus switching.")

section_data = data.copy()
section_data["Section"] = section_data["Nama_Perangkat"].map(SECTION_MAP).fillna("BELUM DIPETAKAN")
section_data["Imax Saat Ini (A)"] = section_data[PHASES].max(axis=1)

# Puncak historis dihitung per switching dan per fasa, termasuk jam kejadian.
hist_long = df.melt(id_vars=["Nama_Perangkat", "Waktu"], value_vars=PHASES,
                    var_name="Fasa", value_name="Arus (A)").dropna(subset=["Arus (A)"])
if not hist_long.empty:
    idx = hist_long.groupby("Nama_Perangkat")["Arus (A)"].idxmax()
    peaks = hist_long.loc[idx, ["Nama_Perangkat", "Waktu", "Fasa", "Arus (A)"]].rename(
        columns={"Waktu": "Waktu Puncak", "Fasa": "Fasa Puncak", "Arus (A)": "Imax Historis (A)"})
    section_data = section_data.merge(peaks, on="Nama_Perangkat", how="left")
else:
    section_data["Imax Historis (A)"] = float("nan")
    section_data["Fasa Puncak"] = "–"
    section_data["Waktu Puncak"] = pd.NaT

section_names = sorted(section_data["Section"].unique())
selected_sections = st.multiselect("Filter section", section_names, default=section_names)
filtered = section_data[section_data["Section"].isin(selected_sections)].copy()
if filtered.empty:
    st.info("Pilih minimal satu section untuk menampilkan analisis.")
else:
    summary = filtered.groupby("Section", as_index=False).agg(
        **{"Jumlah Switching": ("Nama_Perangkat", "nunique"),
           "Imax Saat Ini (A)": ("Imax Saat Ini (A)", "max"),
           "Imax Historis (A)": ("Imax Historis (A)", "max"),
           "Unbalance Tertinggi (%)": ("Unbalance_%", "max")})
    top = filtered.loc[filtered["Imax Saat Ini (A)"].idxmax()] if filtered["Imax Saat Ini (A)"].notna().any() else None
    c1, c2, c3 = st.columns(3)
    c1.metric("Section ditampilkan", len(summary))
    c2.metric("Imax tertinggi saat ini", f"{top['Imax Saat Ini (A)']:,.0f} A" if top is not None else "–")
    c3.metric("Switching dengan Imax tertinggi", top["Nama_Perangkat"] if top is not None else "–")

    st.subheader("Ringkasan arus maksimum per section")
    st.dataframe(summary, hide_index=True, use_container_width=True)
    st.subheader("Rincian switching: arus saat ini dan puncak historis")
    detail_cols = ["Section", "Nama_Perangkat", *PHASES, "Imax Saat Ini (A)",
                   "Imax Historis (A)", "Fasa Puncak", "Waktu Puncak", "Unbalance_%", "Status"]
    st.dataframe(filtered[detail_cols].sort_values(["Section", "Nama_Perangkat"]),
                 hide_index=True, use_container_width=True)
    st.download_button("⬇️ Unduh evaluasi section (CSV)",
                       filtered[detail_cols].to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"evaluasi_section_pwi11_{pd.Timestamp(selected_time):%Y%m%d_%H%M}.csv",
                       mime="text/csv")
    chart_sec = px.bar(summary, x="Section", y=["Imax Saat Ini (A)", "Imax Historis (A)"],
                       barmode="group", title="Imax pada sesi terpilih vs puncak seluruh riwayat")
    chart_sec.update_layout(xaxis_tickangle=-35, yaxis_title="Arus (A)")
    st.plotly_chart(chart_sec, use_container_width=True)

    st.subheader("Tren arus maksimum per section dari waktu ke waktu")
    trend = df.copy()
    trend["Section"] = trend["Nama_Perangkat"].map(SECTION_MAP).fillna("BELUM DIPETAKAN")
    trend = trend[trend["Section"].isin(selected_sections)]
    trend["Imax (A)"] = trend[PHASES].max(axis=1)
    trend = trend.groupby(["Waktu", "Section"], as_index=False)["Imax (A)"].max()
    if not trend.empty:
        st.plotly_chart(px.line(trend, x="Waktu", y="Imax (A)", color="Section", markers=True),
                        use_container_width=True)

st.warning("Pemetaan SECTION_MAP merupakan rancangan awal berdasarkan referensi SLD. "
           "Periksa dan sesuaikan batas section/cabang sebelum dipakai untuk keputusan manuver. "
           "Imax historis adalah nilai terbesar dalam seluruh data Google Sheets yang terbaca, "
           "bukan rating nominal atau batas aman peralatan. Untuk alarm overload diperlukan data rating masing-masing perangkat.")
