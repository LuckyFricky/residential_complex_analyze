import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import os

# ===========================
# ЗАГРУЗКА ДАННЫХ
# ===========================
@st.cache_data
def load_jk_data():
    DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "ZHK_statistics.xlsx")
    if not os.path.exists(DATA_FILE):
        st.error(f"Файл '{DATA_FILE}' не найден.")
        return pd.DataFrame()

    try:
        df = pd.read_excel(DATA_FILE)
        
        # Убедимся, что обязательные колонки есть
        required = ["name", "latitude", "longitude"]
        if not all(col in df.columns for col in required):
            st.error(f"Отсутствуют обязательные колонки: {required}")
            return pd.DataFrame()
        
        # Приведём координаты к числу (на всякий случай)
        df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
        df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
        df = df.dropna(subset=["latitude", "longitude"]).reset_index(drop=True)
        
        # Убедимся, что названия ЖК — строки без лишних пробелов
        df["name"] = df["name"].astype(str).str.strip()
        
        return df
    
    except Exception as e:
        st.error(f"Ошибка при чтении файла: {e}")
        return pd.DataFrame()

df = load_jk_data()

# ===========================
# ПРОВЕРКА ДАННЫХ
# ===========================
if df.empty:
    st.title("🏙️ Дашборд жилых комплексов Москвы")
    st.error("Нет данных. Проверьте файл `ZHK_statistics.xlsx` в папке `data/`.")
    st.stop()

# ===========================
# ВЫБОР ЖК ЧЕРЕЗ ВИДЖЕТ (надёжный способ)
# ===========================
st.subheader("Выберите ЖК")
jk_names = df["name"].tolist()
selected_name = st.selectbox("Жилой комплекс", options=jk_names)

# Найдём данные выбранного ЖК
selected_row = df[df["name"] == selected_name].iloc[0]

# ===========================
# ИНТЕРФЕЙС
# ===========================
st.set_page_config(page_title="Анализ ЖК Москвы", layout="wide")
st.title("🏙️ Дашборд жилых комплексов Москвы")
st.markdown("Выберите ЖК из списка или посмотрите на карте.")

# ===========================
# КАРТА (с фокусом на выбранный ЖК)
# ===========================
m = folium.Map(
    location=[selected_row["latitude"], selected_row["longitude"]],
    zoom_start=13,
    tiles="CartoDB positron"
)

for _, row in df.iterrows():
    folium.Marker(
        location=[float(row["latitude"]), float(row["longitude"])],
        popup=row["name"],
        tooltip=row["name"],
        icon=folium.Icon(
            color="red" if row["name"] == selected_name else "blue"
        )
    ).add_to(m)

st_folium(m, width=900, height=500)

# ===========================
# ДЕТАЛИ
# ===========================
st.subheader("Подробная информация")

jk = selected_row.to_dict()
st.markdown(f"### 🏢 {jk['name']}")

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
    st.write(f"- Обеспеченность машиноместами: {jk.get('percent_of_parking', '—')}")

st.markdown("---")
st.markdown("#### 📐 Архитектурные параметры")
st.write(f"- Мин. высота потолков: {jk.get('min_ceiling_height', '—')} м")
st.write(f"- Макс. высота потолков: {jk.get('max_ceiling_height', '—')} м")
st.write(f"- Этажность: {int(jk.get('min_floors', 0))}–{int(jk.get('max_floors', 0))}")
st.write(f"- Средняя общая площадь квартиры: {jk.get('avg_living_area_m2', '—')} м²")