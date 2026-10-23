from pathlib import Path
import json
import html
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title='Monitoring SLD Purwodadi-11', page_icon='⚡', layout='wide')
BASE = Path(__file__).resolve().parent
SHEET_ID = '1oaerHtNXS-QPNsJzAEd5Ljl54H4pgt32YqfnF-fMiTQ'
SHEET_TAB = 'Realtime_Beban'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
IMAGE_NAMES = ('sld_purwodadi11.jpg', 'sld_purwodadi11.png', 'sld_purwodadi11.jpeg')
# Posisi default diambil dari file cadangan JSON pengguna (koordinat piksel asli 2048 x 935).
# Koordinat diubah menjadi persentase agar mengikuti zoom dan ukuran tampilan.
# Posisi lokal dapat digeser; tombol Reset mengembalikan ke posisi JSON ini.
POSITIONS = {
    'PMT-PWI11': (5.9082, 48.02139),
    'REC-PWI11-50': (17.91992, 48.02139),
    'REC-K2-603-368': (35.69336, 50.26738),
    'LBS-K2-380-2': (42.82227, 45.34759),
    'LBS-K2-380-11D': (42.48047, 27.27273),
    'LBS-K2-11D-99-1': (46.24023, 12.19251),
    'LBS-K2-370-14': (44.62891, 65.88235),
    'LBS-K2-603-408': (47.70508, 48.77005),
    'LBS-K2-603-536': (54.05273, 58.71658),
    'LBS-BL1-421': (64.35547, 59.57219),
    'LBS-BL1-426-2': (64.84375, 65.34759),
}

@st.cache_data(ttl=60, show_spinner='Membaca Google Sheets...')
def load_data():
    if 'gcp_service_account' in st.secrets:
        info = dict(st.secrets['gcp_service_account'])
        info['private_key'] = info['private_key'].replace('\\n', '\n')
        cred = Credentials.from_service_account_info(info, scopes=SCOPES)
    elif (BASE / 'credentials.json').is_file():
        cred = Credentials.from_service_account_file(str(BASE / 'credentials.json'), scopes=SCOPES)
    else:
        raise RuntimeError('Service account belum tersedia di Streamlit Secrets atau credentials.json lokal.')
    client = gspread.authorize(cred)
    worksheet = client.open_by_key(SHEET_ID).worksheet(SHEET_TAB)
    values = worksheet.get_all_values()
    if not values:
        return pd.DataFrame()
    header = [str(c).strip() for c in values[0]]
    df = pd.DataFrame(values[1:], columns=header)
    df.columns = df.columns.str.strip()
    return df


def clean_name(s):
    return str(s).strip().upper().replace('–', '-').replace('—', '-').replace(' ', '')


def number(s):
    return pd.to_numeric(str(s).strip().replace(',', '.'), errors='coerce')


st.title('⚡ Monitoring Real-Time Beban SLD Purwodadi-11')
st.caption('Pantauan seluruh switching pada waktu yang sama • Analisis arus per fasa • Imax • SLD interaktif')
if st.button('🔄 Perbarui data Google Sheets'):
    load_data.clear()
    st.rerun()

try:
    df = load_data()
except Exception as exc:
    st.error('Google Sheets belum dapat dibaca.')
    st.code(f'{type(exc).__name__}: {exc}')
    st.info('Periksa Streamlit Secrets, izin Viewer untuk email service account, dan Google Sheets API.')
    st.stop()

if df.empty:
    st.warning('Spreadsheet belum berisi data.')
    st.stop()

required = ['Timestamp Device_ID', 'Nama_Perangkat', 'Ampere_R', 'Ampere_S', 'Ampere_T', 'Status']
missing = [c for c in required if c not in df.columns]
if missing:
    st.error('Kolom tidak ditemukan: ' + ', '.join(missing))
    st.write('Kolom tersedia:', df.columns.tolist())
    st.stop()

df['Nama_Normal'] = df['Nama_Perangkat'].map(clean_name)
df['Waktu'] = pd.to_datetime(df['Timestamp Device_ID'].astype(str).str.strip(), errors='coerce')
for phase in 'RST':
    df['I_' + phase] = df['Ampere_' + phase].map(number)
df['Imax'] = df[['I_R', 'I_S', 'I_T']].max(axis=1)
df['Iavg'] = df[['I_R', 'I_S', 'I_T']].mean(axis=1)
df['Unbalance_%'] = ((df[['I_R', 'I_S', 'I_T']].sub(df['Iavg'], axis=0).abs().max(axis=1) / df['Iavg'].replace(0, float('nan'))) * 100).round(2)
valid_times = sorted(df['Waktu'].dropna().unique(), reverse=True)
if not valid_times:
    st.error('Format timestamp tidak dapat dibaca.')
    st.stop()
selected_time = st.selectbox('🕒 Pilih waktu pengukuran', valid_times, format_func=lambda x: pd.Timestamp(x).strftime('%d/%m/%Y %H:%M'))
current = df[df['Waktu'] == selected_time].copy().drop_duplicates('Nama_Normal', keep='last')
previous_times = [t for t in valid_times if t < selected_time]
previous = df[df['Waktu'] == previous_times[0]].copy().drop_duplicates('Nama_Normal', keep='last') if previous_times else pd.DataFrame()
if not previous.empty:
    old = previous.set_index('Nama_Normal')[['I_R', 'I_S', 'I_T']]
    for phase in 'RST':
        current['Delta_' + phase] = current['I_' + phase] - current['Nama_Normal'].map(old['I_' + phase])
else:
    for phase in 'RST':
        current['Delta_' + phase] = float('nan')

c1, c2, c3, c4 = st.columns(4)
c1.metric('Switching terbaca', len(current))
c2.metric('Arus tertinggi', f"{current['Imax'].max():.0f} A")
c3.metric('Unbalance tertinggi', f"{current['Unbalance_%'].max():.1f}%")
c4.metric('Data SLD tersedia', f"{sum(n in set(current['Nama_Normal']) for n in POSITIONS)}/{len(POSITIONS)}")

st.subheader('🗺️ SLD interaktif — seluruh switching pada jam yang sama')
st.caption('Kotak dapat digeser secara manual. Posisi disimpan di browser ini. Zoom memperbesar gambar dan seluruh label bersama-sama.')
image_path = next((BASE / n for n in IMAGE_NAMES if (BASE / n).exists()), None)
if image_path is None:
    st.warning('Gambar SLD tidak ditemukan. Pastikan sld_purwodadi11.jpg ada di repository GitHub.')
else:
    import base64
    suffix = image_path.suffix.lower()
    mime = 'image/png' if suffix == '.png' else 'image/jpeg'
    encoded = base64.b64encode(image_path.read_bytes()).decode('ascii')
    # Label selalu dibuat dari POSITIONS, bukan hanya perangkat yang kebetulan ditemukan.
    # Ini memastikan 3 switching yang sebelumnya hilang tetap terwakili.
    index = {r['Nama_Normal']: r for _, r in current.iterrows()}
    markers = []
    for name, (x, y) in POSITIONS.items():
        r = index.get(clean_name(name))
        if r is None:
            label = f'{name} | Belum ada data pada sesi ini'
            missing_data = True
        else:
            label = (f"{name} | R {r['I_R']:.0f} / S {r['I_S']:.0f} / T {r['I_T']:.0f} A | "
                     f"Imax {r['Imax']:.0f} A | UB {r['Unbalance_%']:.1f}%")
            missing_data = False
        markers.append({'id': name, 'x': x, 'y': y, 'text': label, 'missing': missing_data})
    payload = json.dumps(markers, ensure_ascii=False).replace('</', '<\\/')
    img_src = f'data:{mime};base64,{encoded}'
    widget = '''
    <style>
      body {margin:0;font-family:Arial,sans-serif;color:#17212d}
      .toolbar{display:flex;gap:7px;align-items:center;flex-wrap:wrap;margin:0 0 8px}
      button{padding:7px 11px;border:1px solid #cbd5e1;background:#fff;border-radius:6px;cursor:pointer}
      .viewport{height:680px;overflow:auto;border:1px solid #cbd5e1;border-radius:8px;background:#f9fafb}
      #stage{position:relative;width:1600px;line-height:0;transform-origin:top left}
      #base{width:100%;height:auto;display:block;user-select:none;pointer-events:none}
      .tag{position:absolute;z-index:2;transform:translate(-50%,-50%);padding:3px 5px;min-width:85px;max-width:160px;
        line-height:1.25;font-size:10px;font-weight:600;text-align:center;white-space:normal;
        color:#064e3b;border:1px solid #15803d;background:#f0fdf4ee;border-radius:4px;cursor:grab;touch-action:none}
      .tag.missing{background:#fff7ed;border-color:#ea580c;color:#9a3412}
      .tag:active{cursor:grabbing}.hint{font-size:12px;color:#64748b}
    </style>
    <div class="toolbar">
      <button id="minus">−</button><span id="zoomLabel">100%</span><button id="plus">+</button>
      <button id="fit">Pas layar</button><button id="reset">Reset posisi</button>
      <button id="export">Cadangkan posisi JSON</button>
      <span class="hint">Geser kotak dengan mouse • scroll area untuk menjelajah SLD</span>
    </div>
    <div class="viewport" id="viewport"><div id="stage"><img id="base" src="__IMAGE__" alt="SLD Purwodadi 11"/></div></div>
    <script>
      const markers=__MARKERS__;
      const storageKey='sld_pwi11_positions_json_default_v2';
      const viewport=document.getElementById('viewport'), stage=document.getElementById('stage');
      const img=document.getElementById('base');
      let stored={};try{stored=JSON.parse(localStorage.getItem(storageKey)||'{}')}catch(e){}
      let scale=1, naturalWidth=1600, naturalHeight=850;
      function persist(){localStorage.setItem(storageKey,JSON.stringify(stored))}
      function applyScale(){stage.style.width=naturalWidth*scale+'px';stage.style.height=naturalHeight*scale+'px';
        img.style.width='100%';img.style.height='100%';
        document.getElementById('zoomLabel').textContent=Math.round(scale*100)+'%';
        for(const m of markers){const el=document.getElementById('tag-'+m.id);const p=stored[m.id]||m;
          el.style.left=(p.x/100*naturalWidth*scale)+'px';el.style.top=(p.y/100*naturalHeight*scale)+'px';
          el.style.fontSize=Math.max(7,10*scale)+'px';el.style.padding=(3*scale)+'px '+(5*scale)+'px';
          el.style.maxWidth=(160*scale)+'px';el.style.minWidth=(85*scale)+'px';
        }
      }
      for(const m of markers){const el=document.createElement('div');el.className='tag'+(m.missing?' missing':'');
        el.id='tag-'+m.id;el.textContent=m.text;el.title=m.text;stage.appendChild(el);
        el.addEventListener('pointerdown',e=>{e.preventDefault();el.setPointerCapture(e.pointerId);
          const startX=e.clientX,startY=e.clientY;const p=stored[m.id]||m;const initial={x:p.x,y:p.y};
          function move(ev){stored[m.id]={x:Math.max(0,Math.min(100,initial.x+(ev.clientX-startX)/(naturalWidth*scale)*100)),
            y:Math.max(0,Math.min(100,initial.y+(ev.clientY-startY)/(naturalHeight*scale)*100))};applyScale()}
          function end(){el.removeEventListener('pointermove',move);el.removeEventListener('pointerup',end);persist()}
          el.addEventListener('pointermove',move);el.addEventListener('pointerup',end,{once:true});
        });
      }
      img.addEventListener('load',()=>{naturalWidth=img.naturalWidth;naturalHeight=img.naturalHeight;applyScale();fit()});
      function fit(){scale=Math.max(.3,Math.min(1.5,(viewport.clientWidth-16)/naturalWidth));applyScale()}
      document.getElementById('fit').onclick=fit;
      document.getElementById('plus').onclick=()=>{scale=Math.min(2.5,scale+.1);applyScale()};
      document.getElementById('minus').onclick=()=>{scale=Math.max(.3,scale-.1);applyScale()};
      document.getElementById('reset').onclick=()=>{if(confirm('Reset semua posisi label?')){stored={};persist();applyScale()}};
      document.getElementById('export').onclick=()=>{const data=JSON.stringify(Object.fromEntries(markers.map(m=>[m.id,stored[m.id]||{x:m.x,y:m.y}])),null,2);
        const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([data],{type:'application/json'}));
        a.download='posisi_label_sld.json';a.click();URL.revokeObjectURL(a.href)};
      applyScale();
    </script>'''.replace('__MARKERS__', payload).replace('__IMAGE__', img_src)
    components.html(widget, height=750, scrolling=False)

st.subheader('📋 Beban seluruh switching')
view = current[['Nama_Perangkat', 'I_R', 'I_S', 'I_T', 'Imax', 'Unbalance_%', 'Delta_R', 'Delta_S', 'Delta_T', 'Status']].copy()
view.columns = ['Perangkat', 'R (A)', 'S (A)', 'T (A)', 'Imax (A)', 'Unbalance (%)', 'ΔR (A)', 'ΔS (A)', 'ΔT (A)', 'Status']
st.dataframe(view, use_container_width=True, hide_index=True)

st.subheader('📊 Perbandingan beban fasa')
chart = current.set_index('Nama_Perangkat')[['I_R', 'I_S', 'I_T']]
st.bar_chart(chart, stack=False)

st.subheader('📈 Tren beban per jam dan arus maksimum')
selected_device = st.selectbox('Pilih switching', sorted(df['Nama_Perangkat'].dropna().astype(str).str.strip().unique()))
trend = df[df['Nama_Normal'] == clean_name(selected_device)].sort_values('Waktu')
if not trend.empty:
    st.line_chart(trend.set_index('Waktu')[['I_R', 'I_S', 'I_T', 'Imax']])
    st.metric('Imax tertinggi selama periode data', f"{trend['Imax'].max():.0f} A")

st.subheader('🔎 Pemeriksaan 3 switching')
check_names = ['LBS-K2-603-536', 'LBS-BL1-421', 'LBS-BL1-426-2']
check = current[current['Nama_Normal'].isin(check_names)][['Nama_Perangkat', 'I_R', 'I_S', 'I_T', 'Imax']]
st.dataframe(check, hide_index=True, use_container_width=True)
not_found = sorted(set(check_names) - set(current['Nama_Normal']))
if not_found:
    st.warning('Tidak ada data pada sesi ini untuk: ' + ', '.join(not_found))
else:
    st.success('Ketiga switching terbaca dan seluruhnya dibuatkan label pada SLD.')
