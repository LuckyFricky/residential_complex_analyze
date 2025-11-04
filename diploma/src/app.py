import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import os
import numpy as np

# ===========================
# ЗАГРУЗКА ДАННЫХ + РАСЧЁТ ISD
# ===========================
@st.cache_data
def load_jk_data():
    DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "ZHK_statistics.xlsx")
    if not os.path.exists(DATA_FILE):
        st.error(f"Файл '{DATA_FILE}' не найден.")
        return pd.DataFrame()

    try:
        df = pd.read_excel(DATA_FILE)
        required = ["name", "latitude", "longitude", "all_amount", "studio_amount", "avg_living_area_m2"]
        if not all(col in df.columns for col in required):
            st.error(f"Отсутствуют обязательные колонки: {required}")
            return pd.DataFrame()
        
        for col in ["latitude", "longitude", "all_amount", "studio_amount", "avg_living_area_m2"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["latitude", "longitude", "all_amount", "avg_living_area_m2"])
        df["name"] = df["name"].astype(str).str.strip()
        
        # === ISD ===
        df["studio_pct"] = df["studio_amount"] / df["all_amount"]
        df["area_score"] = (35 / df["avg_living_area_m2"]).clip(0, 2)
        score_housing = 0.7 * df["studio_pct"] + 0.3 * df["area_score"]

        flats_per_floor_score = (df["avg_flats_on_floor"] / 8).clip(0, 1)
        parking_share = pd.to_numeric(df["percent_of_parking"], errors="coerce")
        parking_score = (1 - parking_share).clip(0, 1)
        ceiling_score = (2.7 - df["min_ceiling_height"]).clip(0, 1) / 0.5
        floors_score = (df["max_floors"] - 25).clip(0, 10) / 10
        elevators_score = (2 - df["elevators_on_entracne"]).clip(0, 1)

        comfort_score = (
            0.3 * flats_per_floor_score +
            0.25 * parking_score +
            0.2 * ceiling_score +
            0.15 * floors_score +
            0.1 * elevators_score
        ).clip(0, 1)

        df["children_norm"] = (df["children_playing_zone_amount"] / (df["all_amount"] / 300)).fillna(0)
        children_score = (1 - df["children_norm"].clip(0, 1)).clip(0, 1)
        sports_score = (1 - (df["sports_amount"] > 0).astype(int))
        bike_score = (1 - df["bicycle_is"].fillna(0))
        sidewalk_score = (1 - (df["sidewalk_amount"] > 0).astype(int))

        accessibility_sum = (
            df["is_pandus"].fillna(0) +
            df["step_down_platforms_is"].fillna(0) +
            (df["wheelchair_lift_amount"] > 0).astype(int)
        )
        accessibility_score = (3 - accessibility_sum) / 3

        infra_score = (
            0.3 * children_score +
            0.2 * sports_score +
            0.15 * bike_score +
            0.15 * sidewalk_score +
            0.2 * accessibility_score
        ).clip(0, 1)

        df["isd"] = np.round(0.5 * score_housing + 0.3 * comfort_score + 0.2 * infra_score, 3)
        return df
    except Exception as e:
        st.error(f"Ошибка при чтении файла ЖК: {e}")
        return pd.DataFrame()


def load_infrastructure():
    INFRA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "infrastructure.xlsx")
    if not os.path.exists(INFRA_FILE):
        return pd.DataFrame()

    try:
        df = pd.read_excel(INFRA_FILE)
        # Ожидаем колонки: jk_name, name, type, latitude, longitude
        required = ["jk_name", "name", "type", "latitude", "longitude"]
        if not all(col in df.columns for col in required):
            st.warning("Файл infrastructure.xlsx не содержит нужных колонок: jk_name, name, type, latitude, longitude")
            return pd.DataFrame()
        
        df["jk_name"] = df["jk_name"].astype(str).str.strip()
        df["name"] = df["name"].astype(str).str.strip()
        df["type"] = df["type"].astype(str).str.lower()
        df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
        df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
        return df.dropna(subset=["latitude", "longitude"])
    except Exception as e:
        st.error(f"Ошибка при чтении infrastructure.xlsx: {e}")
        return pd.DataFrame()


df_jk = load_jk_data()
df_infra = load_infrastructure()

if df_jk.empty:
    st.title("🏙️ Дашборд жилых комплексов Москвы")
    st.error("Нет данных по ЖК.")
    st.stop()

if "selected_jk_name" not in st.session_state or st.session_state.selected_jk_name not in df_jk["name"].values:
    st.session_state.selected_jk_name = df_jk.iloc[0]["name"]

st.sidebar.title("🏙️ Анализ ЖК")
# Поиск ЖК
search_query = st.sidebar.text_input("🔍 Поиск ЖК", placeholder="Введите название...")

if search_query:
    matched_jks = df_jk[df_jk["name"].str.contains(search_query, case=False, na=False)]
    if not matched_jks.empty:
        candidate = matched_jks.iloc[0]["name"]
        if candidate != st.session_state.selected_jk_name:
            st.session_state.selected_jk_name = candidate
            st.rerun()
    else:
        st.sidebar.warning("ЖК не найден")
st.set_page_config(page_title="Анализ ЖК Москвы", layout="wide")
st.title("🏙️ Дашборд жилых комплексов Москвы")
st.markdown("Кликните по метке на карте, чтобы увидеть подробную информацию.")

# ===========================
# КАРТА
# ===========================
selected_row = df_jk[df_jk["name"] == st.session_state.selected_jk_name].iloc[0]
m = folium.Map(
    location=[selected_row["latitude"], selected_row["longitude"]],
    zoom_start=12,
    tiles="CartoDB positron"
)

# Маркеры ЖК
for _, row in df_jk.iterrows():
    isd_val = row.get("isd", 0)
    color = "red" if isd_val >= 0.6 else "orange" if isd_val >= 0.4 else "green"
    folium.Marker(
        location=[row["latitude"], row["longitude"]],
        popup=row["name"],
        tooltip=f"{row['name']} (ISD: {isd_val:.2f})",
        icon=folium.Icon(color=color, icon="home", prefix="fa")
    ).add_to(m)

# Инфраструктура для выбранного ЖК
if not df_infra.empty:
    infra_for_jk = df_infra[df_infra["jk_name"] == st.session_state.selected_jk_name]
    type_colors = {
        "school": "blue",
        "kindergarten": "orange",
        "metro": "purple",
        "park": "green",
        "shop": "darkred",
        "hospital": "cadetblue",
        "sports": "pink",
        "playground": "lightgreen"
    }
    for _, row in infra_for_jk.iterrows():
        color = type_colors.get(row["type"], "gray")
        folium.Marker(
            location=[row["latitude"], row["longitude"]],
            popup=f"{row['name']} ({row['type']})",
            tooltip=row["name"],
            icon=folium.Icon(color=color, icon="info-sign")
        ).add_to(m)

map_data = st_folium(m, width=900, height=500, returned_objects=["last_object_clicked_popup"])

if map_data and map_data.get("last_object_clicked_popup"):
    clicked_name = map_data["last_object_clicked_popup"]
    if clicked_name in df_jk["name"].values and clicked_name != st.session_state.selected_jk_name:
        st.session_state.selected_jk_name = clicked_name
        st.rerun()

# ===========================
# ДЕТАЛИ
# ===========================
st.subheader("Подробная информация")

if st.session_state.selected_jk_name:
    jk = df_jk[df_jk["name"] == st.session_state.selected_jk_name].iloc[0].to_dict()
    st.markdown(f"### 🏢 {jk['name']}")
    st.metric("Индекс социального дисбаланса (ISD)", f"{jk.get('isd', 0):.3f}")
    st.caption("Чем ближе к 1 — тем сильнее дисбаланс")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Квартиры всего", int(jk.get("all_amount", 0)))
        st.metric("Студии", int(jk.get("studio_amount", 0)))
        st.metric("1-комн.", int(jk.get("1_room_amount", 0)))
    with col2:
        st.metric("2-комн.", int(jk.get("2_room_amount", 0)))
        st.metric("3-комн.", int(jk.get("3_room_amount", 0)))
        st.metric("4+ комнат", int(jk.get("4+_room_amount", 0)))
    with col3:
        st.metric("Лифтов", int(jk.get("elevators_amount", 0)))
        st.metric("Подъездов", int(jk.get("entrances_amount", 0)))
        st.metric("Машиномест", int(jk.get("places_for_cars_in_parking", 0)))

    st.markdown("---")
    st.markdown("#### 📊 Инфраструктура и доступность")
    infra_col1, infra_col2 = st.columns(2)
    with infra_col1:
        st.write(f"- Детских площадок: {int(jk.get('children_playing_zone_amount', 0))}")
        st.write(f"- Спортивных площадок: {int(jk.get('sports_amount', 0))}")
        st.write(f"- Велодорожки: {'Да' if jk.get('bicycle_is') else 'Нет'}")
        st.write(f"- Тротуары: {'Да' if jk.get('sidewalk_amount') else 'Нет'}")
    with infra_col2:
        st.write(f"- Пандус: {'Да' if jk.get('is_pandus') else 'Нет'}")
        st.write(f"- Инвалидных подъёмников: {int(jk.get('wheelchair_lift_amount', 0))}")
        st.write(f"- Понижающие бордюры: {'Да' if jk.get('step_down_platforms_is') else 'Нет'}")

    st.markdown("---")
    st.markdown("#### 📐 Архитектурные параметры")
    st.write(f"- Мин. высота потолков: {jk.get('min_ceiling_height', '—')} м")
    st.write(f"- Макс. высота потолков: {jk.get('max_ceiling_height', '—')} м")
    st.write(f"- Этажность: {int(jk.get('min_floors', 0))}–{int(jk.get('max_floors', 0))}")
    st.write(f"- Средняя площадь квартиры: {jk.get('avg_living_area_m2', '—')} м²")

    # === НАСТОЯЩАЯ ИНФРАСТРУКТУРА РЯДОМ ===
    st.markdown("---")
    st.subheader("📍 Инфраструктура рядом")
    if not df_infra.empty:
        infra_for_jk = df_infra[df_infra["jk_name"] == st.session_state.selected_jk_name]
        if not infra_for_jk.empty:
            for _, row in infra_for_jk.iterrows():
                st.write(f"- **{row['name']}** ({row['type']})")
        else:
            st.write("Нет данных об инфраструктуре для этого ЖК.")
    else:
        st.write("Файл infrastructure.xlsx не загружен или не содержит данных.")

else:
    st.info("Выберите ЖК на карте.")