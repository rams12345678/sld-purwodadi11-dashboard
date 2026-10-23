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
