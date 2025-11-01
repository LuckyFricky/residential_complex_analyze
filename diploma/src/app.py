import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import os
import numpy as np
st.cache_data.clear()
st.cache_resource.clear()
# ===========================
# ЗАГРУЗКА ДАННЫХ ИЗ ПАПКИ
# ===========================

@st.cache_data
def load_jk_data():
    DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
    if not os.path.exists(DATA_DIR):
        st.error(f"Папка '{DATA_DIR}' не найдена.")
        return pd.DataFrame()

    all_dfs = []
    for file in os.listdir(DATA_DIR):
        if file.endswith(".xlsx"):
            filepath = os.path.join(DATA_DIR, file)
            try:
                # Читаем как обычную таблицу с заголовками
                df_one = pd.read_excel(filepath)
                
                # Добавляем имя ЖК
                name = os.path.splitext(file)[0].replace("ZHK_", "").replace("_important", "").replace("_", " ").title()
                df_one["name"] = name
                
                all_dfs.append(df_one)
                
            except Exception as e:
                st.warning(f"Ошибка при чтении {file}: {e}")
    
    if not all_dfs:
        return pd.DataFrame()
    
    df = pd.concat(all_dfs, ignore_index=True)
    
    # Приводим координаты к числовому типу
    df["lat"] = pd.to_numeric(df["Ширина"], errors="coerce")
    df["lon"] = pd.to_numeric(df["Долгота"], errors="coerce")
    df = df.dropna(subset=["lat", "lon"]).reset_index(drop=True)
    
    return df

df = load_jk_data()

# ===========================
# ПРОВЕРКА ДАННЫХ
# ===========================
if df.empty:
    st.title("🏙️ Дашборд жилых комплексов Москвы")
    st.error("Нет данных. Положите Excel-файлы в папку `data/`.")
    st.stop()

# ===========================
# СОСТОЯНИЕ ВЫБРАННОГО ЖК
# ===========================
if "selected_jk" not in st.session_state:
    st.session_state.selected_jk = None

# ===========================
# ИНТЕРФЕЙС
# ===========================
st.set_page_config(page_title="Анализ ЖК Москвы", layout="wide")
st.title("🏙️ Дашборд жилых комплексов Москвы")
st.markdown("Кликните по метке на карте, чтобы увидеть подробную информацию.")

# ===========================
# КАРТА
# ===========================
moscow_center = [55.7522, 37.6156]
m = folium.Map(location=moscow_center, zoom_start=12, tiles="CartoDB positron")

for _, row in df.iterrows():
    try:
        lat = float(row["lat"])
        lon = float(row["lon"])
    except (TypeError, ValueError):
        continue  # пропустить, если координаты некорректны

    popup_html = f"""
<div style="width: 220px;">
    <b>{row['name']}</b><br>
    <button onclick="window.parent.location.search='?jk_name={row['name'].replace(' ', '%20')}'"
            style="padding: 6px 10px; background-color: #4CAF50; color: white; border: none; border-radius: 4px; margin-top: 8px; cursor: pointer;">
        Подробнее
    </button>
</div>
"""
    folium.Marker(
        location=[lat, lon],
        popup=folium.Popup(popup_html, max_width=250),
        tooltip=row["name"]
    ).add_to(m)

st_folium(m, width=900, height=500)

# ===========================
# ОБРАБОТКА ВЫБОРА ЧЕРЕЗ URL
# ===========================
jk_name = st.query_params.get("jk_name", None)

if jk_name:
    selected_rows = df[df["name"] == jk_name]
    if not selected_rows.empty:
        st.session_state.selected_jk = selected_rows.iloc[0].to_dict()
else:
    st.session_state.selected_jk = None
# ===========================
# ДЕТАЛИ
# ===========================
st.subheader("Подробная информация")

if st.session_state.selected_jk:
    jk = st.session_state.selected_jk
    
    st.markdown(f"### 🏢 {jk['name']}")
    
    # Основные метрики
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Квартиры всего", int(jk.get("Количество жилых помещений", 0)))
        st.metric("Студии", int(jk.get("Количество студий", 0)))
        st.metric("1-комн.", int(jk.get("Количество однокомнатных квартир", 0)))
    with col2:
        st.metric("2-комн.", int(jk.get("Количество двухкомнатных квартир", 0)))
        st.metric("3-комн.", int(jk.get("Количество трехкомнатных квартир", 0)))
        st.metric("4+ комнат", int(jk.get("Количество 4 и 4+ комнатных квартир", 0)))
    with col3:
        st.metric("Лифтов", int(jk.get("Количество лифтов", 0)))
        st.metric("Подъездов", int(jk.get("Количество подъездов", 0)))
        st.metric("Машиномест (паркинг)", int(jk.get("Количество машино-мест в паркинге", 0)))

    st.markdown("---")
    st.markdown("#### 📊 Инфраструктура и доступность")
    infra_col1, infra_col2 = st.columns(2)
    with infra_col1:
        st.write(f"- Детских площадок: {int(jk.get('Количество детских площадок', 0))}")
        st.write(f"- Спортивных площадок: {int(jk.get('Количество спортивных площадок', 0))}")
        st.write(f"- Велодорожки: {'Да' if jk.get('Наличие велосипедных дорожек') else 'Нет'}")
        st.write(f"- Тротуары: {'Да' if jk.get('Наличие тротуаров') else 'Нет'}")
    with infra_col2:
        st.write(f"- Пандус: {'Да' if jk.get('Наличие пандуса') else 'Нет'}")
        st.write(f"- Инвалидных подъёмников: {int(jk.get('Количество инвалидных подъемников', 0))}")
        st.write(f"- Понижающие бордюры: {'Да' if jk.get('Наличие понижающих площадок') else 'Нет'}")
        st.write(f"- Обеспеченность машиноместами: {jk.get('Обеспеченность машиноместами', '—')}")

    st.markdown("---")
    st.markdown("#### 📐 Архитектурные параметры")
    st.write(f"- Мин. высота потолков: {jk.get('Минимальная высота потолков', '—')} м")
    st.write(f"- Макс. высота потолков: {jk.get('Максимальная высота потолков', '—')} м")
    st.write(f"- Этажность: {int(jk.get('Минимальное количество этажей', 0))}–{int(jk.get('Максимальное количество этажей', 0))}")
    st.write(f"- Средняя общая площадь квартиры: {jk.get('Средняя общая площадь, м2', '—')} м²")
else:
    st.info("Выберите ЖК на карте для просмотра деталей.")
