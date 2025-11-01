import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import os
import numpy as np
# ===========================
# ЗАГРУЗКА ДАННЫХ ИЗ ПАПКИ
# ===========================

def clean_numeric(x):
    if pd.isna(x):
        return np.nan
    try:
        return float(str(x).strip().replace(",", "."))
    except:
        return np.nan
        
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
    
    # Убедимся, что координаты числовые
    df["lat"] = pd.to_numeric(df["Ширина"], errors="coerce")
    df["lon"] = pd.to_numeric(df["Долгота"], errors="coerce")
    df = df.dropna(subset=["lat", "lon"])
    
    return df

df = load_jk_data()

st.write("Загруженные данные:")
st.dataframe(df[["name", "lat", "lon"]])
st.write("Типы данных:")
st.write(df[["lat", "lon"]].dtypes)
st.write("Пример данных:")
st.dataframe(df[["name", "Ширина", "Долгота"]])

# ===========================
# ПРОВЕРКА ДАННЫХ
# ===========================
if df.empty:
    st.title("🏙️ Дашборд жилых комплексов Москвы")
    st.error("Нет данных. Положите Excel-файлы в папку `data/`.")
    st.stop()

# Убедимся, что координаты числовые


# Переименуем для удобства
df = df.rename(columns={"Ширина": "lat", "Долгота": "lon"})
df = df.dropna(subset=["lat", "lon"])


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
    popup_html = f"""
    <div style="width: 220px;">
        <b>{row['name']}</b><br>
        <a href="?jk_name={row['name']}" target="_self" style="text-decoration: none;">
            <button style="padding: 6px 10px; background-color: #4CAF50; color: white; border: none; border-radius: 4px; margin-top: 8px;">
                Подробнее
            </button>
        </a>
    </div>
    """
    folium.Marker(
        location=[row["lat"], row["lon"]],
        popup=folium.Popup(popup_html, max_width=250),
        tooltip=row["name"]
    ).add_to(m)

st_folium(m, width=900, height=500)

# ===========================
# ОБРАБОТКА ВЫБОРА ЧЕРЕЗ URL
# ===========================
query_params = st.experimental_get_query_params()
jk_name = query_params.get("jk_name", [None])[0]

if jk_name:
    selected_rows = df[df["name"] == jk_name]
    if not selected_rows.empty:
        st.session_state.selected_jk = selected_rows.iloc[0].to_dict()

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
