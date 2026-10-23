"""Dashboard V3.1 – Monitoring Beban SLD Purwodadi-11.
Deploy app.py + requirements.txt + sld_purwodadi11.jpg; keep credentials in Streamlit Secrets.
"""
from pathlib import Path
from io import BytesIO
import base64
import json
import html
import streamlit.components.v1 as components
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from PIL import Image
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Monitoring Beban SLD PWI11 V4.3", page_icon="⚡", layout="wide")
BASE = Path(__file__).resolve().parent
SPREADSHEET_ID = "1oaerHtNXS-QPNsJzAEd5Ljl54H4pgt32YqfnF-fMiTQ"
WORKSHEET_NAME = "Realtime_Beban"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
PHASES = ["Ampere_R", "Ampere_S", "Ampere_T"]
# Koordinat pada gambar asli 2048 x 935 piksel.
# anchor = pusat simbol switching; label = pusat kotak informasi.
# Ubah angka ini jika gambar SLD diperbarui.
SLD_POSITIONS = {
    "PMT-PWI11":       {"anchor": (121, 449), "label": (143, 348)},
    "REC-PWI11-50":    {"anchor": (367, 449), "label": (490, 348)},
    "REC-K2-603-368": {"anchor": (1096, 348), "label": (1065, 255)},
    "LBS-K2-380-2":   {"anchor": (1210, 269), "label": (1200, 195)},
    "LBS-K2-380-11D": {"anchor": (1210, 269), "label": (1110, 110)},
    "LBS-K2-11D-99-1":{"anchor": (None, None), "label": (1430, 105)},
    "LBS-K2-370-14":  {"anchor": (1250, 474), "label": (1320, 680)},
    "LBS-K2-603-408": {"anchor": (1329, 348), "label": (1400, 235)},
    "LBS-K2-603-536": {"anchor": (1464, 348), "label": (143, 262)},
    "LBS-BL1-421":    {"anchor": (1717, 348), "label": (144, 263)},
    "LBS-BL1-426-2": {"anchor": (1630, 474), "label": (145, 264)},
}
# CATATAN: Beberapa titik cabang di atas perlu verifikasi pada gambar asli.
# Khusus K2-11D-99-1 belum diberikan anchor karena simbolnya tidak terlihat
# secara pasti pada gambar ini. Label tetap tampil tanpa garis penunjuk.

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
    """SLD dengan label drag-and-drop; posisi tersimpan di browser pengguna."""
    image_file = next((BASE / f for f in ("sld_purwodadi11.jpg", "sld_purwodadi11.png", "sld_purwodadi11.jpeg") if (BASE / f).exists()), None)
    if image_file is None:
        st.warning("Gambar sld_purwodadi11.jpg belum ada di repository.")
        return
    img = Image.open(image_file).convert("RGB")
    w, h = img.size
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=92)
    uri = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    indexed = data.set_index("Nama_Perangkat")
    labels = []
    # Sertakan SEMUA nama perangkat dari sesi, meskipun belum punya titik koordinat.
    # Perangkat yang belum dipetakan ditaruh di area daftar bawah SLD dan dapat digeser.
    all_names = list(dict.fromkeys([*SLD_POSITIONS.keys(), *data["Nama_Perangkat"].dropna().astype(str).tolist()]))
    extra_names = [n for n in all_names if n not in SLD_POSITIONS]
    for name in all_names:
        if name in SLD_POSITIONS:
            pos = SLD_POSITIONS[name]
        else:
            ix = extra_names.index(name)
            pos = {"anchor": (None, None), "label": (210 + (ix % 5) * 330, 820 + (ix // 5) * 30)}
        record = indexed.loc[name] if name in indexed.index else None
        if isinstance(record, pd.DataFrame):
            record = record.iloc[-1]
        if record is not None and all(pd.notna(record[p]) for p in PHASES):
            vals = [float(record[p]) for p in PHASES]
            display = "R/S/T: " + " / ".join(f"{v:g}" for v in vals) + " A"
            bad = pd.notna(record["Unbalance_%"]) and record["Unbalance_%"] > threshold
            color = "#b91c1c" if bad else "#15803d"
            bg = "#fee2e2" if bad else "#f0fdf4"
        else:
            display, color, bg = "Data tidak tersedia", "#6b7280", "#f3f4f6"
        labels.append({"name":name,"x":pos["label"][0],"y":pos["label"][1],
                       "ax":pos["anchor"][0],"ay":pos["anchor"][1],
                       "display":display,"color":color,"bg":bg})
    payload = json.dumps(labels, ensure_ascii=False).replace("<", "\u003c")
    # Komponen HTML terisolasi: data arus hanya ditampilkan; tidak mengubah spreadsheet.
    page = r'''<!DOCTYPE html><html><head><meta charset="utf-8"><style>
    body{font-family:Arial,sans-serif;margin:0;color:#172033;background:#fff}
    .toolbar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:5px 0 10px}
    button{border:1px solid #cbd5e1;background:#f8fafc;padding:8px 12px;border-radius:7px;cursor:pointer}
    button.primary{background:#166534;color:white;border-color:#166534}
    button:disabled{opacity:.5;cursor:default}
    .hint{font-size:12px;color:#475569;margin:8px 0}
    .viewport{overflow:auto;border:1px solid #e2e8f0;border-radius:8px;background:white}
    svg{display:block;width:100%;height:auto;min-width:0;touch-action:none;user-select:none}.viewport{height:660px;overscroll-behavior:contain}.toolbar .zoom{font-weight:700;min-width:38px}
    .label{cursor:grab}.label.dragging{cursor:grabbing}
    .label rect{stroke-width:1.2;rx:3;ry:3}
    .label text{font-size:7px;fill:#111827;pointer-events:none}
    .label text.name{font-weight:700;font-size:7.5px}
    .connector{pointer-events:none;stroke-width:1.6;fill:none}
    .anchor-dot{pointer-events:none}
    #status{font-size:12px;color:#475569}
    </style></head><body>
    <div class="toolbar">
      <button id="edit" class="primary">✥ Mode geser: AKTIF</button>
      <button id="reset">↺ Reset posisi</button>
      <button id="export">↓ Cadangkan posisi JSON</button>
      <button id="minus" class="zoom">−</button><span id="zoomval">100%</span><button id="plus" class="zoom">+</button><button id="fit">Pas layar</button><button id="actual">100%</button>
      <span id="status">Geser kotak dengan mouse. Posisi tersimpan otomatis pada browser ini.</span>
    </div>
    <div class="viewport" id="viewport"><svg id="diagram" viewBox="0 0 __W__ __H__" xmlns="http://www.w3.org/2000/svg">
      <image href="__IMAGE__" width="__W__" height="__H__"/>
      <g id="connectors"></g><g id="labels"></g>
    </svg></div>
    <p class="hint">Semua perangkat yang memiliki data pada jam terpilih ditampilkan. Kotak beban dapat digeser pada mode edit. Gunakan tombol +/− atau roda mouse untuk zoom; geser area kosong untuk memindahkan tampilan (pan). Posisi kotak disimpan di browser ini.</p>
    <script>
    const original=__LABELS__;
    const key='pwi11_sld_positions_v4'; // tetap gunakan posisi tersimpan versi lama
    const svg=document.getElementById('diagram'), labelLayer=document.getElementById('labels'), lineLayer=document.getElementById('connectors');
    const NS='http://www.w3.org/2000/svg';
    let saved={}; try{saved=JSON.parse(localStorage.getItem(key)||'{}')}catch(e){}
    let editable=true, drag=null, pan=null, scale=1;
    const viewport=document.getElementById('viewport');
    const state=original.map(d=>({...d,...(saved[d.name]||{})}));
    const node=(tag,attrs,parent)=>{const e=document.createElementNS(NS,tag);Object.entries(attrs||{}).forEach(([k,v])=>e.setAttribute(k,String(v)));parent.appendChild(e);return e};
    function persist(){try{localStorage.setItem(key,JSON.stringify(Object.fromEntries(state.map(d=>[d.name,{x:d.x,y:d.y,ax:d.ax,ay:d.ay}]))));document.getElementById('status').textContent='Posisi tersimpan otomatis pada browser ini.'}catch(e){document.getElementById('status').textContent='Penyimpanan browser tidak tersedia. Gunakan Cadangkan posisi JSON.'}}
    function render(){labelLayer.replaceChildren();lineLayer.replaceChildren();
      for(const d of state){
        const width=Math.max(92,Math.min(154,d.name.length*4.8+16));const height=25;
        const g=node('g',{class:'label',transform:`translate(${d.x} ${d.y})`,'data-name':d.name},labelLayer);
        node('rect',{x:-width/2,y:-height/2,width,height,fill:d.bg,stroke:d.color},g);
        const a=node('text',{x:0,y:-2,'text-anchor':'middle',class:'name'},g);a.textContent=d.name;
        const b=node('text',{x:0,y:7,'text-anchor':'middle'},g);b.textContent=d.display;
        g.addEventListener('pointerdown',e=>{if(!editable)return;e.preventDefault();const p=point(e);drag={d,start:p,x:d.x,y:d.y,ax:d.ax,ay:d.ay,moveAnchor:e.shiftKey};g.classList.add('dragging');g.setPointerCapture(e.pointerId)});
        g.addEventListener('pointermove',e=>{if(!drag||drag.d!==d)return;const p=point(e);const dx=p.x-drag.start.x,dy=p.y-drag.start.y;
          if(drag.moveAnchor){if(drag.ax!=null){d.ax=Math.max(0,Math.min(__W__,drag.ax+dx));d.ay=Math.max(0,Math.min(__H__,drag.ay+dy))}}
          else{d.x=Math.max(0,Math.min(__W__,drag.x+dx));d.y=Math.max(0,Math.min(__H__,drag.y+dy))}
          renderDrag(d,g);
        });
        const end=e=>{if(drag&&drag.d===d){drag=null;persist();render()}};
        g.addEventListener('pointerup',end);g.addEventListener('pointercancel',end);
      }
    }
    function renderDrag(d,g){g.setAttribute('transform',`translate(${d.x} ${d.y})`)}
    // Semua label berada pada SVG yang sama dengan gambar: zoom tidak menggeser koordinat.
    function fitScale(){return viewport.clientWidth / __W__}
    function setZoom(next,cx=viewport.clientWidth/2,cy=viewport.clientHeight/2){
      const old=scale, min=fitScale()*0.55, max=fitScale()*5;
      scale=Math.max(min,Math.min(max,next));
      const sx=viewport.scrollLeft+cx,sy=viewport.scrollTop+cy;
      svg.style.width= (__W__*scale)+'px';
      svg.style.height=(__H__*scale)+'px';
      viewport.scrollLeft=sx*(scale/old)-cx;
      viewport.scrollTop=sy*(scale/old)-cy;
      document.getElementById('zoomval').textContent=Math.round(scale/fitScale()*100)+'%';
    }
    function resetFit(){scale=fitScale();svg.style.width=(__W__*scale)+'px';svg.style.height=(__H__*scale)+'px';viewport.scrollLeft=0;viewport.scrollTop=0;document.getElementById('zoomval').textContent='100%'}
    document.getElementById('plus').onclick=()=>setZoom(scale*1.25);
    document.getElementById('minus').onclick=()=>setZoom(scale/1.25);
    document.getElementById('fit').onclick=resetFit;
    document.getElementById('actual').onclick=()=>setZoom(1);
    viewport.addEventListener('wheel',e=>{e.preventDefault();const r=viewport.getBoundingClientRect();setZoom(scale*(e.deltaY<0?1.12:1/1.12),e.clientX-r.left,e.clientY-r.top)},{passive:false});
    svg.addEventListener('pointerdown',e=>{if(e.target.closest('.label'))return;pan={x:e.clientX,y:e.clientY,l:viewport.scrollLeft,t:viewport.scrollTop,id:e.pointerId};svg.setPointerCapture(e.pointerId)});
    svg.addEventListener('pointermove',e=>{if(!pan||pan.id!==e.pointerId)return;viewport.scrollLeft=pan.l+pan.x-e.clientX;viewport.scrollTop=pan.t+pan.y-e.clientY});
    svg.addEventListener('pointerup',e=>{if(pan&&pan.id===e.pointerId)pan=null});
    svg.addEventListener('pointercancel',()=>pan=null);
    function point(e){const p=svg.createSVGPoint();p.x=e.clientX;p.y=e.clientY;return p.matrixTransform(svg.getScreenCTM().inverse())}
    document.getElementById('edit').onclick=()=>{editable=!editable;document.getElementById('edit').textContent=editable?'✥ Mode geser: AKTIF':'🔒 Mode geser: NONAKTIF'};
    document.getElementById('reset').onclick=()=>{if(!confirm('Kembalikan semua kotak ke posisi awal?'))return;state.splice(0,state.length,...original.map(d=>({...d})));persist();render()};
    document.getElementById('export').onclick=()=>{const contents=JSON.stringify(Object.fromEntries(state.map(d=>[d.name,{x:Math.round(d.x),y:Math.round(d.y),ax:d.ax==null?null:Math.round(d.ax),ay:d.ay==null?null:Math.round(d.ay)}])),null,2);
      const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([contents],{type:'application/json'}));a.download='posisi_label_sld_pwi11.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)};
    render();resetFit();
    </script></body></html>'''
    page = page.replace("__W__", str(w)).replace("__H__", str(h)).replace("__IMAGE__", uri).replace("__LABELS__", payload)
    components.html(page, height=755, scrolling=False)
    st.caption("Label lebih ringkas. Semua switching dari Google Sheets ikut ditampilkan; perangkat yang belum dipetakan bisa digeser. Koordinat label dapat diatur langsung di web. Penyimpanan otomatis hanya di browser yang digunakan, bukan di GitHub atau Google Sheets.")

st.title("⚡ Monitoring Beban SLD Purwodadi-11 | V4.3")
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
