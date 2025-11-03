import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import os

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
        
        # Приведение к числу
        for col in ["latitude", "longitude", "all_amount", "studio_amount", "avg_living_area_m2"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["latitude", "longitude", "all_amount", "avg_living_area_m2"])

        df["name"] = df["name"].astype(str).str.strip()
        
        # === РАСЧЁТ ИНДЕКСА СОЦИАЛЬНОГО ДИСБАЛАНСА (ISD) ===
        df["studio_pct"] = df["studio_amount"] / df["all_amount"]
        # Нормируем площадь: 35 м² — ориентир минимальной комфортной площади на человека (для 1-комн.)
        df["area_score"] = 35 / df["avg_living_area_m2"]
        df["area_score"] = df["area_score"].clip(lower=0, upper=2)  # ограничиваем выбросы
        
        # Веса: студии (70%), площадь (30%)
        df["isd"] = 0.7 * df["studio_pct"] + 0.3 * df["area_score"]
        df["isd"] = df["isd"].round(3)
        
        return df
    
    except Exception as e:
        st.error(f"Ошибка при чтении файла: {e}")
        return pd.DataFrame()


# Загрузка инфраструктуры (оставим на будущее, но сейчас не используется для ISD)
def load_infrastructure():
    INFRA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "infrastructure.xlsx")
    if not os.path.exists(INFRA_FILE):
        return pd.DataFrame()

    try:
        df = pd.read_excel(INFRA_FILE)
        df["name"] = df["name"].astype(str).str.strip()
        df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
        df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
        return df.dropna(subset=["latitude", "longitude"])
    except:
        return pd.DataFrame()


df_jk = load_jk_data()
df_infra = load_infrastructure()

# ===========================
# ПРОВЕРКА ДАННЫХ
# ===========================
if df_jk.empty:
    st.title("🏙️ Дашборд жилых комплексов Москвы")
    st.error("Нет данных. Проверьте файл `ZHK_statistics.xlsx` в папке `data/`.")
    st.stop()

# ===========================
# СИНХРОНИЗАЦИЯ СОСТОЯНИЯ
# ===========================
if "selected_jk_name" not in st.session_state or st.session_state.selected_jk_name not in df_jk["name"].values:
    st.session_state.selected_jk_name = df_jk.iloc[0]["name"]

# ===========================
# ИНТЕРФЕЙС
# ===========================
st.set_page_config(page_title="Анализ ЖК Москвы", layout="wide")
st.title("🏙️ Дашборд жилых комплексов Москвы")
st.markdown("Кликните по метке на карте, чтобы увидеть подробную информацию.")

# ===========================
# КАРТА
# ===========================
selected_row = df_jk[df_jk["name"] == st.session_state.selected_jk_name].iloc[0]
m = folium.Map(
    location=[selected_row["latitude"], selected_row["longitude"]],
    zoom_start=11,
    tiles="CartoDB positron"
)

# Добавляем маркеры ЖК с цветом по ISD
for _, row in df_jk.iterrows():
    isd_val = row.get("isd", 0)
    if isd_val >= 0.6:
        color = "red"
    elif isd_val >= 0.4:
        color = "orange"
    else:
        color = "green"
    
    folium.Marker(
        location=[row["latitude"], row["longitude"]],
        popup=row["name"],
        tooltip=f"{row['name']} (ISD: {isd_val:.2f})",
        icon=folium.Icon(color=color, icon="home", prefix="fa")
    ).add_to(m)

map_data = st_folium(m, width=900, height=500, returned_objects=["last_object_clicked_popup"])

# Обновление выбора по клику
if map_data and map_data.get("last_object_clicked_popup"):
    clicked_name = map_data["last_object_clicked_popup"]
    if clicked_name in df_jk["name"].values and clicked_name != st.session_state.selected_jk_name:
        st.session_state.selected_jk_name = clicked_name
        st.rerun()

# ===========================
# ДЕТАЛИ ЖК
# ===========================
st.subheader("Подробная информация")

if st.session_state.selected_jk_name:
    jk = df_jk[df_jk["name"] == st.session_state.selected_jk_name].iloc[0].to_dict()
    st.markdown(f"### 🏢 {jk['name']}")
    
    # === НОВОЕ: Индекс социального дисбаланса ===
    st.metric("Индекс социального дисбаланса (ISD)", f"{jk.get('isd', 0):.3f}")
    st.caption("Чем ближе к 1 — тем сильнее дисбаланс (много малогабариток, низкая площадь на квартиру)")

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
        st.metric("Машиномест (паркинг)", int(jk.get("places_for_cars_in_parking", 0)))

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
        st.write(f"- Обеспеченность машиноместами: {jk.get('percent_of_parking', '—').round(3)}")

    st.markdown("---")
    st.markdown("#### 📐 Архитектурные параметры")
    st.write(f"- Мин. высота потолков: {jk.get('min_ceiling_height', '—')} м")
    st.write(f"- Макс. высота потолков: {jk.get('max_ceiling_height', '—')} м")
    st.write(f"- Этажность: {int(jk.get('min_floors', 0))}–{int(jk.get('max_floors', 0))}")
    st.write(f"- Средняя общая площадь квартиры: {jk.get('avg_living_area_m2', '—')} м²")

    # Инфраструктура рядом (из infrastructure.xlsx, если будет расширена)
    st.markdown("---")
    st.subheader("📍 Инфраструктура рядом")
    st.write("Данные по инфраструктуре пока дублируют ЖК. В будущем сюда будут подгружаться школы, метро и т.д.")

else:
    st.info("Выберите ЖК на карте для просмотра деталей.")