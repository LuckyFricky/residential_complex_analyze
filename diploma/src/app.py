import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

# ===========================
# 1. ДАННЫЕ (заменить на свои)
# ===========================
@st.cache_data
def load_data():
    return pd.DataFrame({
        "id": [1, 2, 3],
        "name": ["ЖК 'Небо'", "ЖК 'Река'", "ЖК 'Парк'"],
        "address": [
            "г. Москва, Ленинский проспект, 100",
            "г. Москва, ул. Профсоюзная, 50",
            "г. Москва, Дмитровское шоссе, 30"
        ],
        "lat": [55.6893, 55.6482, 55.8521],
        "lon": [37.5412, 37.5689, 37.5306],
        "total_apartments": [600, 420, 300],
        "studios": [180, 100, 60],
        "one_room": [240, 180, 120],
        "two_room": [150, 180, 90],
        "three_plus_room": [30, 60, 30],
        "elevators": [8, 6, 4],
        "parking_spots": [400, 250, 180],
        "playgrounds": [3, 2, 1],
        "sports_areas": [2, 1, 1],
        "has_bike_paths": [True, False, True],
        "ceiling_min": [2.7, 2.65, 2.8],
        "floors_min": [10, 9, 8],
        "floors_max": [25, 18, 12]
    })

df = load_data()

# ===========================
# 2. ИНИЦИАЛИЗАЦИЯ СОСТОЯНИЯ
# ===========================
if "selected_jk" not in st.session_state:
    st.session_state.selected_jk = None

# ===========================
# 3. ЗАГОЛОВОК
# ===========================
st.set_page_config(page_title="Анализ ЖК Москвы", layout="wide")
st.title("🏙️ Дашборд жилых комплексов Москвы")
st.markdown("Кликните по метке на карте, чтобы увидеть подробную информацию о ЖК.")

# ===========================
# 4. КАРТА С КЛИКАБЕЛЬНЫМИ МЕТКАМИ
# ===========================
st.subheader("Карта ЖК")

# Центрируем на Москве
moscow_center = [55.7522, 37.6156]
m = folium.Map(location=moscow_center, zoom_start=10, tiles="CartoDB positron")

# Добавляем маркеры
for _, row in df.iterrows():
    # Создаём HTML-попап с кнопкой (на самом деле — ссылка, эмулирующая выбор)
    popup_html = f"""
    <div style="width: 200px;">
        <b>{row['name']}</b><br>
        {row['address']}<br><br>
        <a href="?jk_id={row['id']}" target="_self" style="text-decoration: none;">
            <button style="padding: 6px 10px; background-color: #4CAF50; color: white; border: none; border-radius: 4px;">
                Показать детали
            </button>
        </a>
    </div>
    """
    folium.Marker(
        location=[row["lat"], row["lon"]],
        popup=folium.Popup(popup_html, max_width=250),
        tooltip=row["name"]
    ).add_to(m)

# Отображаем карту
map_data = st_folium(m, width=800, height=500)

# ===========================
# 5. ОБРАБОТКА ВЫБОРА ЖК ЧЕРЕЗ URL-ПАРАМЕТР
# ===========================
# Streamlit не поддерживает прямые callback'и, но можно парсить query params
from urllib.parse import parse_qs, urlparse
import streamlit as st

query_params = st.experimental_get_query_params()
jk_id = query_params.get("jk_id", [None])[0]

if jk_id is not None:
    try:
        jk_id = int(jk_id)
        selected_row = df[df["id"] == jk_id].iloc[0]
        st.session_state.selected_jk = selected_row
    except (ValueError, IndexError):
        st.session_state.selected_jk = None

# ===========================
# 6. ПАНЕЛЬ С ДЕТАЛЯМИ
# ===========================
st.subheader("Подробная информация")

if st.session_state.selected_jk is not None:
    jk = st.session_state.selected_jk
    
    st.markdown(f"### 🏢 {jk['name']}")
    st.markdown(f"**Адрес:** {jk['address']}")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Всего квартир", jk["total_apartments"])
        st.metric("Студии", jk["studios"])
        st.metric("1-комн.", jk["one_room"])
    with col2:
        st.metric("2-комн.", jk["two_room"])
        st.metric("3+ комнат", jk["three_plus_room"])
        st.metric("Этажность", f"{jk['floors_min']}–{jk['floors_max']}")
    with col3:
        st.metric("Лифтов", jk["elevators"])
        st.metric("Машиномест", jk["parking_spots"])
        st.metric("Детских площадок", jk["playgrounds"])

    st.markdown("---")
    st.markdown("#### 📊 Дополнительно")
    st.write(f"- Мин. высота потолков: {jk['ceiling_min']} м")
    st.write(f"- Спортивных площадок: {jk['sports_areas']}")
    st.write(f"- Велодорожки: {'Да' if jk['has_bike_paths'] else 'Нет'}")

else:
    st.info("Выберите ЖК на карте, чтобы увидеть подробности.")
