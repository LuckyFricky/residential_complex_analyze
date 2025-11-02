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
        
        # Приведём координаты к числу (на всякий случае)
        df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
        df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
        df = df.dropna(subset=["latitude", "longitude"]).reset_index(drop=True)
        
        # Убедимся, что названия ЖК — строки без лишних пробелов
        df["name"] = df["name"].astype(str).str.strip()
        
        return df
    
    except Exception as e:
        st.error(f"Ошибка при чтении файла: {e}")
        return pd.DataFrame()

# Загрузка инфраструктуры
def load_infrastructure():  # УБРАЛИ @st.cache_data
    INFRA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "infrastructure.xlsx")
    if not os.path.exists(INFRA_FILE):
        st.error(f"Файл '{INFRA_FILE}' не найден.")
        return pd.DataFrame()

    try:
        df = pd.read_excel(INFRA_FILE)
        
        # Приведём к нужным типам
        df["JK_name"] = df["JK_name"].astype(str).str.strip()
        df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
        df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
        df = df.dropna(subset=["latitude", "longitude"])
        
        # Переименуем колонку для совместимости
        df = df.rename(columns={"JK_name": "jk_name", "longtitude": "longitude"})
        
        return df
    
    except Exception as e:
        st.error(f"Ошибка при чтении файла инфраструктуры: {e}")
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
# СИНХРОНИЗАЦИЯ СОСТОЯНИЯ С URL
# ===========================
jk_name_from_url = st.query_params.get("jk_name", None)

# Если в URL есть jk_name и оно существует в данных
if jk_name_from_url and jk_name_from_url in df_jk["name"].values:
    st.session_state.selected_jk_name = jk_name_from_url
# Если в URL нет, но в session_state есть, используем его
elif "selected_jk_name" not in st.session_state or st.session_state.selected_jk_name not in df_jk["name"].values:
    # Иначе — первый ЖК
    st.session_state.selected_jk_name = df_jk.iloc[0]["name"] if not df_jk.empty else None
else:
    # Оставляем текущее состояние
    pass

# ===========================
# ИНТЕРФЕЙС
# ===========================
st.set_page_config(page_title="Анализ ЖК Москвы", layout="wide")
st.title("🏙️ Дашборд жилых комплексов Москвы")
st.markdown("Кликните по метке на карте, чтобы увидеть подробную информацию.")

# ===========================
# КАРТА
# ===========================
# Центрируем карту на выбранном ЖК
selected_row = df_jk[df_jk["name"] == st.session_state.selected_jk_name].iloc[0]
m = folium.Map(
    location=[selected_row["latitude"], selected_row["longitude"]],
    zoom_start=12,  # Уменьшили зум, чтобы видеть все ЖК
    tiles="CartoDB positron"
)

# Добавляем маркеры для ВСЕХ ЖК
for _, row in df_jk.iterrows():
    folium.Marker(
        location=[row["latitude"], row["longitude"]],
        popup=row["name"],
        tooltip=row["name"],
        icon=folium.Icon(
            color="red" if row["name"] == st.session_state.selected_jk_name else "lightblue",
            icon="home",
            prefix="fa"
        )
    ).add_to(m)

# Фильтруем инфраструктуру для выбранного ЖК
infra_for_jk = df_infra[df_infra["jk_name"] == st.session_state.selected_jk_name]

# Добавляем инфраструктуру
for _, row in infra_for_jk.iterrows():
    # Определяем цвет иконки по типу
    icon_color = {
        "school": "blue",
        "kindergarten": "orange",
        "park": "green",
        "metro": "purple",
        "shop": "darkred",
        "hospital": "cadetblue"
    }.get(row["type"], "gray")

    folium.Marker(
        location=[row["latitude"], row["longitude"]],
        popup=f"{row['name']} ({row['type']})",
        tooltip=row["name"],
        icon=folium.Icon(color=icon_color, popupAnchor=(0, -10))
    ).add_to(m)

# Отображаем карту
map_data = st_folium(
    m,
    width=900,
    height=500,
    returned_objects=["last_object_clicked_popup"]
)

# ===========================
# ОБНОВЛЕНИЕ ВЫБОРА ПО КЛИКУ НА КАРТЕ
# ===========================
if map_data and map_data.get("last_object_clicked_popup"):
    clicked_name = map_data["last_object_clicked_popup"]
    if clicked_name in df_jk["name"].values:
        if clicked_name != st.session_state.selected_jk_name:
            st.session_state.selected_jk_name = clicked_name
            st.query_params.jk_name = clicked_name  # Обновляем URL
            st.rerun()  # Принудительно перезапускаем

# ===========================
# ДЕТАЛИ ЖК + ИНФРАСТРУКТУРА
# ===========================
st.subheader("Подробная информация")

if st.session_state.selected_jk_name:
    jk = df_jk[df_jk["name"] == st.session_state.selected_jk_name].iloc[0].to_dict()
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

    # ===========================
    # ИНФРАСТРУКТУРА РЯДОМ
    # ===========================
    st.markdown("---")
    st.subheader("📍 Инфраструктура рядом")

    if not infra_for_jk.empty:
        for _, infra in infra_for_jk.iterrows():
            st.write(f"- **{infra['name']}** ({infra['type']}) — {infra.get('distance m', '—')} м")
    else:
        st.write("Инфраструктура не найдена.")

else:
    st.info("Выберите ЖК на карте для просмотра деталей.")