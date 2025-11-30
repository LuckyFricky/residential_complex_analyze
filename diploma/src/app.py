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
        parking_raw = pd.to_numeric(df["percent_of_parking"], errors="coerce")
        if parking_raw.max() > 2:
            parking_share = parking_raw / 100
        else:
            parking_share = parking_raw
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
        df["jk_name"] = df["jk_name"].astype(str).str.strip()
        df["name"] = df["name"].astype(str).str.strip()
        df["type"] = df["type"].astype(str).str.lower()
        df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
        df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
        return df.dropna(subset=["latitude", "longitude"])
    except Exception as e:
        st.error(f"Ошибка при чтении infrastructure.xlsx: {e}")
        return pd.DataFrame()


# ===========================
# ОСНОВНАЯ ЛОГИКА
# ===========================
df_jk = load_jk_data()
df_infra = load_infrastructure()

if df_jk.empty:
    st.title("🏙️ Дашборд жилых комплексов Москвы")
    st.error("Нет данных по ЖК.")
    st.stop()

# ===========================
# САЙДБАР: ВЫБОР РЕЖИМА
# ===========================
st.sidebar.title("🎛️ Режим работы")
mode = st.sidebar.radio("Выберите режим:", ["Изучение ЖК", "Сравнение ЖК"])

jk_names = df_jk["name"].tolist()
default_a = jk_names[0]
default_b = jk_names[1] if len(jk_names) > 1 else jk_names[0]

if mode == "Изучение ЖК":
    # === Инициализация ===
    selected_jk = None
    jk_data = None
    filtered_df = df_jk  # по умолчанию — все ЖК

    st.sidebar.markdown("### 🧭 Фильтры")
    
    max_isd = st.sidebar.slider("Макс. ISD", 0.0, 1.0, 1.0, 0.01, key="max_isd")
    with_bike = st.sidebar.checkbox("Только с велодорожками", value=False, key="bike_filter")
    with_pandus = st.sidebar.checkbox("Только с пандусом", value=False, key="pandus_filter")
    high_rise = st.sidebar.checkbox("Более 20 этажей", value=False, key="high_rise_filter")
    min_3room = st.sidebar.number_input("Мин. кол-во 3-комнатных", min_value=0, value=0, step=10, key="min_3room")

    # Применение фильтров
    filtered_df = df_jk.copy()
    filtered_df = filtered_df[filtered_df["isd"] <= max_isd]
    if with_bike:
        filtered_df = filtered_df[filtered_df["bicycle_is"] == 1]
    if with_pandus:
        filtered_df = filtered_df[filtered_df["is_pandus"] == 1]
    if high_rise:
        filtered_df = filtered_df[filtered_df["max_floors"] > 20]
    if min_3room > 0:
        filtered_df = filtered_df[filtered_df["3_room_amount"] >= min_3room]

    # Выбор ЖК
    if filtered_df.empty:
        st.sidebar.warning("Нет ЖК, удовлетворяющих фильтрам.")
    else:
        jk_names_filtered = filtered_df["name"].tolist()
        selected_jk = st.sidebar.selectbox(
            "Выберите ЖК",
            jk_names_filtered,
            index=None,
            placeholder="Выберите жилой комплекс...",
            key="jk_single"
        )
        if selected_jk is not None and selected_jk in filtered_df["name"].values:
            jk_data = filtered_df[filtered_df["name"] == selected_jk].iloc[0].to_dict()

    # === Определение параметров карты ===
    if selected_jk is not None and jk_data is not None:
        center_lat, center_lng = jk_data["latitude"], jk_data["longitude"]
        zoom = 13
        display_jk_df = filtered_df
    else:
        center_lat, center_lng = df_jk["latitude"].mean(), df_jk["longitude"].mean()
        zoom = 11
        display_jk_df = filtered_df if not filtered_df.empty else df_jk

    # === Отображение информации ===
    if selected_jk is None or jk_data is None:
        st.info("🏙️ **Добро пожаловать!**\n\nВыберите жилой комплекс в сайдбаре, чтобы увидеть подробную информацию.")
    else:
        st.subheader(f"🔍 Подробная информация: 🏢 {selected_jk}")
        jk = jk_data
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

        st.markdown("---")
        st.subheader("📍 Инфраструктура рядом")
        if not df_infra.empty:
            current_infra = df_infra[df_infra["jk_name"] == selected_jk]
            if not current_infra.empty:
                for _, row in current_infra.iterrows():
                    st.write(f"- **{row['name']}** ({row['type']})")
            else:
                st.write("Нет данных об инфраструктуре для этого ЖК.")
        else:
            st.write("Файл infrastructure.xlsx не загружен.")
        
elif mode == "Сравнение ЖК":
    jk_a = st.sidebar.selectbox("ЖК A", jk_names, index=0)
    jk_b = st.sidebar.selectbox("ЖК B", jk_names, index=1 if len(jk_names) > 1 else 0)
    jk_a_data = df_jk[df_jk["name"] == jk_a].iloc[0].to_dict()
    jk_b_data = df_jk[df_jk["name"] == jk_b].iloc[0].to_dict()
    center_lat = (jk_a_data["latitude"] + jk_b_data["latitude"]) / 2
    center_lng = (jk_a_data["longitude"] + jk_b_data["longitude"]) / 2
    zoom = 12
    display_jk_df = df_jk  # в режиме сравнения — все ЖК

# ===========================
# КАРТА — ДИНАМИЧЕСКАЯ ПОД ФИЛЬТР
# ===========================
st.set_page_config(page_title="Анализ ЖК Москвы", layout="wide")
st.title("🏙️ Дашборд жилых комплексов Москвы")

# Определяем центр карты
if mode == "Изучение ЖК":
    if selected_jk is not None and jk_data is not None:
        center_lat, center_lng = jk_data["latitude"], jk_data["longitude"]
        zoom = 13
        display_jk_df = filtered_df
    else:
        center_lat, center_lng = df_jk["latitude"].mean(), df_jk["longitude"].mean()
        zoom = 11
        display_jk_df = filtered_df if not filtered_df.empty else df_jk

    
# Создаём карту
m = folium.Map(location=[center_lat, center_lng], zoom_start=zoom, tiles="CartoDB positron")

# Отображаем ТОЛЬКО ЖК из display_jk_df (отфильтрованные или все)
for _, row in display_jk_df.iterrows():
    isd_val = row.get("isd", 0)
    color = "red" if isd_val >= 0.6 else "orange" if isd_val >= 0.4 else "green"
    folium.Marker(
        location=[row["latitude"], row["longitude"]],
        popup=f"{row['name']}<br>ISD: {isd_val:.2f}",
        tooltip=row["name"],
        icon=folium.Icon(color=color, icon="home", prefix="fa")
    ).add_to(m)

# Инфраструктура
if not df_infra.empty:
    infra_to_show = []
    if mode == "Изучение ЖК" and selected_jk:
        infra_to_show = [selected_jk]
    elif mode == "Сравнение ЖК":
        infra_to_show = [jk_a, jk_b]
    
    type_colors = {
        "school": "blue", "kindergarten": "orange", "metro": "purple",
        "park": "green", "shop": "darkred", "hospital": "cadetblue",
        "sports": "pink", "playground": "lightgreen"
    }
    for jk_name in infra_to_show:
        current_infra = df_infra[df_infra["jk_name"] == jk_name]
        for _, row in current_infra.iterrows():
            color = type_colors.get(row["type"], "gray")
            folium.Marker(
                location=[row["latitude"], row["longitude"]],
                popup=f"{row['name']} ({row['type']})",
                tooltip=row["name"],
                icon=folium.Icon(color=color, icon="info-sign")
            ).add_to(m)

st_folium(m, width=900, height=500)

# ===========================
# ОСНОВНОЙ КОНТЕНТ
# ===========================
if mode == "Изучение ЖК":
    st.subheader(f"🔍 Подробная информация: 🏢 {selected_jk}")
    jk = jk_data
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

    st.markdown("---")
    st.subheader("📍 Инфраструктура рядом")
    if not df_infra.empty:
        current_infra = df_infra[df_infra["jk_name"] == selected_jk]
        if not current_infra.empty:
            for _, row in current_infra.iterrows():
                st.write(f"- **{row['name']}** ({row['type']})")
        else:
            st.write("Нет данных об инфраструктуре для этого ЖК.")
    else:
        st.write("Файл infrastructure.xlsx не загружен.")

elif mode == "Сравнение ЖК":
    st.subheader(f"🆚 Сравнение: {jk_a} vs {jk_b}")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(f"### 🏢 {jk_a}")
        st.metric("ISD", f"{jk_a_data['isd']:.3f}")
        st.metric("Квартиры", int(jk_a_data["all_amount"]))
        st.metric("Студии", int(jk_a_data["studio_amount"]))
    with col_b:
        st.markdown(f"### 🏢 {jk_b}")
        st.metric("ISD", f"{jk_b_data['isd']:.3f}")
        st.metric("Квартиры", int(jk_b_data["all_amount"]))
        st.metric("Студии", int(jk_b_data["studio_amount"]))

    st.markdown("#### 🔍 Ключевые различия")
    
    # ISD
    isd_diff = jk_b_data["isd"] - jk_a_data["isd"]
    if abs(isd_diff) < 0.01:
        st.write("✅ **Социальный баланс**: Оба ЖК одинаково сбалансированы.")
    elif isd_diff > 0:
        st.write(f"✅ **Социальный баланс**: **{jk_a} более сбалансирован** (ISD ниже на {isd_diff:.3f})")
    else:
        st.write(f"✅ **Социальный баланс**: **{jk_b} более сбалансирован** (ISD ниже на {abs(isd_diff):.3f})")

    # Студии
    studio_a, studio_b = jk_a_data["studio_amount"], jk_b_data["studio_amount"]
    if studio_a > 0 and studio_b > 0:
        pct = (studio_a - studio_b) / studio_b * 100
        if abs(pct) < 5:
            st.write("🏢 **Студии**: Почти одинаковое количество.")
        elif pct > 0:
            st.write(f"🏢 **Студии**: В **{jk_a}** на {pct:.0f}% больше студий.")
        else:
            st.write(f"🏢 **Студии**: В **{jk_b}** на {abs(pct):.0f}% больше студий.")
    elif studio_a > studio_b:
        st.write(f"🏢 **Студии**: Только в **{jk_a}** есть студии.")
    elif studio_b > studio_a:
        st.write(f"🏢 **Студии**: Только в **{jk_b}** есть студии.")
    else:
        st.write("🏢 **Студии**: В обоих ЖК студий нет.")

    # Средняя площадь
    area_a, area_b = jk_a_data.get("avg_living_area_m2", 0), jk_b_data.get("avg_living_area_m2", 0)
    if area_a > 0 and area_b > 0:
        area_diff = (area_a - area_b) / area_b * 100
        if abs(area_diff) < 3:
            st.write("📐 **Средняя площадь**: Почти одинаковая.")
        elif area_diff > 0:
            st.write(f"📐 **Средняя площадь**: В **{jk_a}** квартиры на {area_diff:.0f}% просторнее.")
        else:
            st.write(f"📐 **Средняя площадь**: В **{jk_b}** квартиры на {abs(area_diff):.0f}% просторнее.")
