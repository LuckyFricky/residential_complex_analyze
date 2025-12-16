import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import os
import numpy as np

st.set_page_config(page_title="Анализ ЖК Москвы", layout="wide")


# ===========================
# ЗАГРУЗКА ДАННЫХ + РАСЧЁТ ISD (УЛУЧШЕННЫЙ)
# ===========================
@st.cache_data
def load_jk_data():
    DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data",
                             "ZHK_statistics.xlsx")
    if not os.path.exists(DATA_FILE):
        st.error(f"Файл '{DATA_FILE}' не найден.")
        return pd.DataFrame()

    try:
        df = pd.read_excel(DATA_FILE)
        required = ["name", "latitude", "longitude", "all_amount"]
        if not all(col in df.columns for col in required):
            st.error(f"Отсутствуют обязательные колонки: {required}")
            return pd.DataFrame()

        # Конвертируем числовые колонки
        numeric_cols = [
            'latitude', 'longitude', 'all_amount', 'studio_amount',
            '1_room_amount', '2_room_amount', '3_room_amount',
            '4+_room_amount', 'avg_flats_on_floor', 'not_living_amount',
            'places_for_cars_in_parking', 'guest_places_for_cars_on_territory',
            'guest_places_for_cars_near_territory', 'percent_of_parking',
            'amount_other_not_living', 'living_area_m2', 'avg_living_area_m2',
            'min_ceiling_height', 'max_ceiling_height', 'min_floors',
            'max_floors', 'elevators_amount', 'entrances_amount',
            'elevators_on_entracne', 'children_playing_zone_amount',
            'sports_amount', 'bicycle_is', 'sidewalk_amount',
            'garbage_area_amount', 'step_down_platforms_is', 'is_pandus',
            'wheelchair_lift_amount'
        ]

        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.dropna(subset=["latitude", "longitude", "all_amount"])
        df["name"] = df["name"].astype(str).str.strip()

        # === РАСШИРЕННЫЙ РАСЧЕТ ISD ===
        # 1. ЖИЛЬЕ (25%) - демографический баланс
        df["total_flats"] = df["all_amount"].fillna(0)
        df["studio_pct"] = df["studio_amount"].fillna(
            0) / df["total_flats"].replace(0, 1)  # защита от деления на 0
        df["large_flats_pct"] = (
            df["3_room_amount"].fillna(0) +
            df["4+_room_amount"].fillna(0)) / df["total_flats"].replace(0, 1)
        df["area_deviation"] = np.abs(df["avg_living_area_m2"].fillna(60) -
                                      60) / 60
        df["non_residential"] = df["not_living_amount"].fillna(
            0) / df["total_flats"].replace(0, 1)

        df["housing_score"] = (  # ✅ ПРИСВОИТЬ КОЛОНКЕ
            0.4 * df["studio_pct"].clip(0, 0.3) + 0.3 *
            (1 - df["large_flats_pct"].clip(0, 0.3)) +
            0.2 * df["area_deviation"].clip(0, 1) +
            0.1 * df["non_residential"].clip(0, 0.2)).clip(0, 1)

        # 2. КОМФОРТ/ПЛОТНОСТЬ (30%)
        df["flats_per_floor"] = df["avg_flats_on_floor"].fillna(6)
        df["parking_raw"] = pd.to_numeric(df["percent_of_parking"],
                                          errors="coerce").fillna(0)
        parking_share = df["parking_raw"] / 100 if df["parking_raw"].max(
        ) > 2 else df["parking_raw"]
        df["parking_deficit"] = (1 - parking_share.clip(0, 1)) * (
            df["places_for_cars_in_parking"].fillna(0) /
            df["total_flats"].replace(0, 1) < 0.5)

        df["comfort_score"] = (  # ✅ ПРИСВОИТЬ КОЛОНКЕ
            0.25 * (df["flats_per_floor"] / 8).clip(0, 1) +
            0.25 * df["parking_deficit"] + 0.15 *
            ((2.7 - df["min_ceiling_height"].fillna(2.7)) / 0.5).clip(0, 1) +
            0.20 * ((df["max_floors"].fillna(25) - 25) / 10).clip(0, 1) +
            0.15 *
            ((2 - df["elevators_on_entracne"].fillna(1)) / 1).clip(0, 1)).clip(
                0, 1)

        # 3. ИНФРАСТРУКТУРА (25%)
        df["children_norm"] = df["children_playing_zone_amount"].fillna(0) / (
            df["total_flats"].replace(0, 1) / 300)
        df["infra_score"] = (  # ✅ ПРИСВОИТЬ КОЛОНКЕ
            0.25 * (1 - df["children_norm"].clip(0, 1)) + 0.15 *
            (1 - (df["sports_amount"].fillna(0) > 0).astype(int)) + 0.10 *
            (1 - df["bicycle_is"].fillna(0)) + 0.10 *
            (1 - (df["sidewalk_amount"].fillna(0) > 0).astype(int)) + 0.20 *
            (df["garbage_area_amount"].fillna(0) == 0).astype(int) + 0.20 *
            ((df["max_floors"].fillna(0) > 5) &
             (df["elevators_amount"].fillna(0) == 0)).astype(int)).clip(0, 1)

        # 4. ДОСТУПНОСТЬ (20%)
        accessibility_sum = (
            df["is_pandus"].fillna(0) +
            df["step_down_platforms_is"].fillna(0) +
            (df["wheelchair_lift_amount"].fillna(0) > 0).astype(int) +
            (df["entrances_amount"].fillna(1) > 0).astype(int))
        df["accessibility_score"] = (
            4 - accessibility_sum.clip(0, 4)) / 4  # ✅ ПРИСВОИТЬ КОЛОНКЕ

        # ИТОГОВЫЙ ISD
        df["isd"] = np.round(
            0.25 * df["housing_score"] + 0.30 * df["comfort_score"] +
            0.25 * df["infra_score"] + 0.20 * df["accessibility_score"],
            3).clip(0, 1)

        return df
    except Exception as e:
        st.error(f"Ошибка при чтении файла ЖК: {e}")
        return pd.DataFrame()


def load_infrastructure():
    INFRA_FILE = os.path.join(os.path.dirname(__file__), "..", "data",
                              "infrastructure.xlsx")
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
# ОСНОВНАЯ ЛОГИКА (остальной код без изменений)
# ===========================
df_jk = load_jk_data()
df_infra = load_infrastructure()

if df_jk.empty:
    st.title("🏙️ Дашборд жилых комплексов Москвы")
    st.error("Нет данных по ЖК.")
    st.stop()

# ===========================
# ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ
# ===========================
if "selected_jk" not in st.session_state:
    st.session_state.selected_jk = "None"
if "filters_applied" not in st.session_state:
    st.session_state.filters_applied = False

# ===========================
# САЙДБАР (ЕДИНСТВЕННЫЙ!)
# ===========================
st.sidebar.title("🎛️ Режим работы")
mode = st.sidebar.radio("Выберите режим:", ["Изучение ЖК", "Сравнение ЖК"],
                        key="mode_radio")

jk_names = df_jk["name"].tolist()

# === ИНИЦИАЛИЗАЦИЯ ПЕРЕМЕННЫХ ===
center_lat, center_lng, zoom = 55.7558, 37.6176, 11
jk_data = None
show_infra = False
selected_jk = st.session_state.selected_jk

if mode == "Изучение ЖК":
    st.sidebar.markdown("### 🎯 Фильтры")

    # === ЗАГРУЗКА ФИЛЬТРОВ ИЗ SESSION_STATE (если есть) ===
    max_isd = st.sidebar.slider("Макс. ISD",
                                0.0,
                                1.0,
                                1.0,
                                0.01,
                                key="max_isd")
    max_studio = st.sidebar.slider("Макс. студий (%)",
                                   0.0,
                                   1.0,
                                   1.0,
                                   0.05,
                                   key="max_studio")
    min_family = st.sidebar.slider("Мин. семейного (%)",
                                   0.0,
                                   1.0,
                                   0.0,
                                   0.05,
                                   key="min_family")
    min_parking = st.sidebar.slider("Мин. парковка (%)",
                                    0.0,
                                    2.0,
                                    0.0,
                                    0.05,
                                    key="min_parking")
    max_floors = st.sidebar.slider("Макс. этажность",
                                   1,
                                   50,
                                   50,
                                   key="max_floors")
    with_bike = st.sidebar.checkbox("Велодорожки", key="with_bike")
    with_children = st.sidebar.checkbox("Детские площадки",
                                        key="with_children")
    with_pandus = st.sidebar.checkbox("Пандусы", key="with_pandus")

    # === ФИЛЬТРАЦИЯ (всегда обновляется на основе текущих значений)
    filtered_df = df_jk.copy()
    filtered_df = filtered_df[filtered_df["isd"] <= max_isd]
    filtered_df = filtered_df[filtered_df["studio_pct"] <= max_studio]
    filtered_df = filtered_df[filtered_df["large_flats_pct"] >= min_family]
    filtered_df = filtered_df[filtered_df["parking_raw"] >= min_parking]
    filtered_df = filtered_df[filtered_df["max_floors"] <= max_floors]
    if with_bike: filtered_df = filtered_df[filtered_df["bicycle_is"] == 1]
    if with_children:
        filtered_df = filtered_df[filtered_df["children_playing_zone_amount"] >
                                  0]
    if with_pandus: filtered_df = filtered_df[filtered_df["is_pandus"] == 1]

    st.sidebar.markdown("---")
    st.sidebar.metric("Найдено ЖК", len(filtered_df))

    # === ЗАГРУЗКА ВЫБРАННОГО ЖК ПОСЛЕ ФИЛЬТРАЦИИ ===
    jk_data = None
    show_infra = False
    if st.session_state.selected_jk != "None":
        match = filtered_df[filtered_df["name"] ==
                            st.session_state.selected_jk]
        if not match.empty:
            jk_data = match.iloc[0].to_dict()
            show_infra = True
        else:
            # Если выбранный ЖК не прошёл фильтр — сбросим
            jk_data = None
            show_infra = False

    if not filtered_df.empty:
        filtered_df_display = filtered_df.copy()
        filtered_df_display["display_name"] = filtered_df_display.apply(
            lambda row: f"{row['name']} (ISD: {row['isd']:.3f})", axis=1)
        display_options = ["None"
                           ] + filtered_df_display["display_name"].tolist()

        selected_display = st.sidebar.selectbox("🎯 Выберите ЖК",
                                                display_options,
                                                index=0,
                                                key="jk_select")

        if st.sidebar.button("🔍 Применить выбор",
                             type="primary",
                             key="apply_btn"):
            if selected_display != "None":
                st.session_state.selected_jk = selected_display.split(
                    " (ISD:")[0]
                st.session_state.filters_applied = True
            else:
                st.session_state.selected_jk = "None"
                st.session_state.filters_applied = False
            st.rerun()
    else:
        st.sidebar.warning("❌ Нет подходящих ЖК")

elif mode == "Сравнение ЖК":
    # Инициализация в session_state
    if "jk_a" not in st.session_state:
        st.session_state.jk_a = "None"
    if "jk_b" not in st.session_state:
        st.session_state.jk_b = "None"
    if "compare_applied" not in st.session_state:
        st.session_state.compare_applied = False

    # Добавляем "None" в начало списка
    jk_names_with_none = ["None"] + jk_names

    # Выпадающие списки
    jk_a_name = st.sidebar.selectbox(
        "ЖК A",
        jk_names_with_none,
        index=0 if st.session_state.jk_a == "None" else
        jk_names_with_none.index(st.session_state.jk_a),
        key="jk_a_select")
    jk_b_name = st.sidebar.selectbox(
        "ЖК B",
        jk_names_with_none,
        index=0 if st.session_state.jk_b == "None" else
        jk_names_with_none.index(st.session_state.jk_b),
        key="jk_b_select")

    # ✅ НЕ обновляем session_state, если compare_applied = True
    if not st.session_state.compare_applied:
        # Обновляем session_state при изменении выбора
        if jk_a_name != st.session_state.jk_a or jk_b_name != st.session_state.jk_b:
            st.session_state.jk_a = jk_a_name
            st.session_state.jk_b = jk_b_name
            # Сбрасываем флаг, если выбор поменялся
            st.session_state.compare_applied = False
            #st.rerun()

    # Кнопка "Применить"
    if st.sidebar.button("🔍 Применить выбор",
                         type="primary",
                         key="apply_compare_btn_unique"):
        # Используем текущие значения из selectbox
        if jk_a_name != "None" and jk_b_name != "None":
            if jk_a_name != jk_b_name:
                # Обновляем session_state
                st.session_state.jk_a = jk_a_name
                st.session_state.jk_b = jk_b_name
                st.session_state.compare_applied = True
            else:
                st.sidebar.warning(
                    "⚠️ Выбраны одинаковые ЖК. Пожалуйста, выберите разные ЖК для сравнения."
                )
        else:
            st.sidebar.warning("⚠️ Пожалуйста, выберите оба ЖК.")
        #st.rerun()

    # === ЗАГРУЗКА ДАННЫХ ТОЛЬКО ЕСЛИ КНОПКА НАЖАТА И ВСЁ ВАЛИДНО ===
    if st.session_state.compare_applied and st.session_state.jk_a != "None" and st.session_state.jk_b != "None":
        jk_a_data = df_jk[df_jk["name"] ==
                          st.session_state.jk_a].iloc[0].to_dict()
        jk_b_data = df_jk[df_jk["name"] ==
                          st.session_state.jk_b].iloc[0].to_dict()

        # ✅ Присваиваем переменные для рендера
        jk_a = st.session_state.jk_a
        jk_b = st.session_state.jk_b

        center_lat = (jk_a_data["latitude"] + jk_b_data["latitude"]) / 2
        center_lng = (jk_a_data["longitude"] + jk_b_data["longitude"]) / 2
        zoom = 12
    else:
        jk_a_data = None
        jk_b_data = None
        # ✅ Присваиваем None, чтобы избежать NameError
        jk_a = None
        jk_b = None
        center_lat, center_lng = 55.7558, 37.6176
        zoom = 11

# ===========================
# КАРТА (ВНЕ САЙДБАРА! НА ТОМ ЖЕ УРОВНЕ)
# ===========================

st.title("🏙️ Дашборд жилых комплексов Москвы")
m = folium.Map(location=[center_lat, center_lng],
               zoom_start=zoom,
               tiles="CartoDB positron")

# 1. ВСЕГДА все ЖК
for _, row in df_jk.iterrows():
    isd_val = row.get("isd", 0)
    color = "red" if isd_val >= 0.6 else "orange" if isd_val >= 0.4 else "green"
    folium.Marker([row["latitude"], row["longitude"]],
                  popup=f"{row['name']}<br>ISD: {isd_val:.3f}",
                  tooltip=row["name"],
                  icon=folium.Icon(color=color, icon="home",
                                   prefix="fa")).add_to(m)

# 2. Инфраструктура ТОЛЬКО при выборе (Изучение ЖК)
if mode == "Изучение ЖК" and show_infra and selected_jk != "None" and not df_infra.empty:
    current_infra = df_infra[df_infra["jk_name"] == selected_jk]
    for _, row in current_infra.iterrows():
        color = {
            "school": "blue",
            "kindergarten": "orange",
            "metro": "purple",
            "park": "green"
        }.get(row["type"], "darkblue")
        folium.Marker(
            [row["latitude"], row["longitude"]],
            popup=f"{row['name']} ({row['type']}) — рядом с {selected_jk}",
            icon=folium.Icon(color=color, icon="info-sign")).add_to(m)

# 3. Инфраструктура для СРАВНЕНИЯ (два ЖК)
if mode == "Сравнение ЖК" and st.session_state.compare_applied:
    for jk_name in [st.session_state.jk_a, st.session_state.jk_b]:
        if jk_name != "None":
            current_infra = df_infra[df_infra["jk_name"] == jk_name]
            for _, row in current_infra.iterrows():
                color = {
                    "school": "blue",
                    "kindergarten": "orange",
                    "metro": "purple",
                    "park": "green"
                }.get(row["type"], "gray")
                folium.Marker(
                    [row["latitude"], row["longitude"]],
                    popup=f"{row['name']} ({row['type']}) — {jk_name}",
                    icon=folium.Icon(color=color, icon="info-sign")).add_to(m)

st_folium(m, width=900, height=500)

# ===========================
# ОСНОВНОЙ КОНТЕНТ
# ===========================
if mode == "Изучение ЖК" and (selected_jk is None or jk_data is None):
    st.info(
        "🏙️ **Добро пожаловать!**\n\nВыберите жилой комплекс в сайдбаре, чтобы увидеть подробную информацию."
    )
elif mode == "Изучение ЖК" and selected_jk is not None and jk_data is not None:
    st.subheader(f"🔍 Подробная информация: 🏢 {selected_jk}")
    jk = jk_data
    st.metric("Индекс социального дисбаланса (ISD)", f"{jk.get('isd', 0):.3f}")
    st.caption("Чем ближе к 1 — тем сильнее дисбаланс")

    # === РАЗВЁРНУТЫЙ ISD ПО КОМПОНЕНТАМ ===
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🏠 Жилье", f"{jk.get('housing_score', 0):.3f}", "вес 25%")
    with col2:
        st.metric("🏗️ Комфорт", f"{jk.get('comfort_score', 0):.3f}", "вес 30%")
    with col3:
        st.metric("🌳 Инфраструктура", f"{jk.get('infra_score', 0):.3f}",
                  "вес 25%")
    with col4:
        st.metric("♿ Доступность", f"{jk.get('accessibility_score', 0):.3f}",
                  "вес 20%")

    st.markdown("---")

    # КВАРТИРЫ
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Квартиры всего", int(jk.get("all_amount", 0)))

        # --- Студии: норма ≤ 20% ---
        studio_pct = jk.get("studio_pct", 0.0)
        if studio_pct > 0.20:
            # плохо: красный, стрелка вниз
            st.metric(
                "Студии (%)",
                f"{studio_pct:.0%}",
                delta=f"{studio_pct:.0%}",
                delta_color="inverse"  # красный + ↓
            )
        else:
            # хорошо: зелёный, без стрелки вниз
            st.metric("Студии (%)", f"{studio_pct:.0%}", delta="норма ≤ 20%")

        st.metric("1-комн.", int(jk.get("1_room_amount", 0)))

    with col2:
        st.metric("2-комн.", int(jk.get("2_room_amount", 0)))

        # --- Большие квартиры: норма ≥ 20% ---
        large_pct = jk.get("large_flats_pct", 0.0)
        if large_pct < 0.20:
            # дефицит больших квартир — плохо
            st.metric(
                "4+ и 3-комн. (%)",
                f"{large_pct:.0%}",
                delta=f"{large_pct:.0%}",
                delta_color="inverse"  # красный + ↓ (мало больших)
            )
        else:
            st.metric("4+ и 3-комн. (%)",
                      f"{large_pct:.0%}",
                      delta="норма ≥ 20%")

        st.metric("3-комн.", int(jk.get("3_room_amount", 0)))

    with col3:
        st.metric("Лифтов", int(jk.get("elevators_amount", 0)))
        st.metric("Подъездов", int(jk.get("entrances_amount", 0)))

        # --- Парковка: норма ≥ 100% ---
        parking_raw = jk.get("parking_raw", 0.0)  # уже в долях (0–1)
        if parking_raw < 1.0:
            # нехватка парковки — плохо
            st.metric(
                "Машиноместа (%)",
                f"{parking_raw:.0%}",
                delta=f"{parking_raw:.0%}",
                delta_color="inverse"  # красный + ↓ (дефицит)
            )
        else:
            st.metric("Машиноместа (%)",
                      f"{parking_raw:.0%}",
                      delta="норма ≥ 100%")

    st.markdown("---")

    # ИНФРАСТРУКТУРА И ДОСТУПНОСТЬ
    infra_col1, infra_col2 = st.columns(2)
    with infra_col1:
        # Детские площадки — чем меньше нормы, тем хуже
        total_flats = jk.get("total_flats", 0) or 0
        if total_flats < 100:
            norm_children = 1
        else:
            norm_children = int(total_flats / 300) if total_flats else 0
        children = int(jk.get("children_playing_zone_amount", 0))
        if children < norm_children and norm_children > 0:
            st.metric(
                "Детские площадки",
                children,
                delta=f"норма {norm_children}",
                delta_color="inverse"  # нехватка — плохо
            )
        else:
            st.metric("Детские площадки",
                      children,
                      delta=f"норма {norm_children}")

        st.metric("Спортивные", int(jk.get("sports_amount", 0)))
        st.metric("Велодорожки", "Да" if jk.get("bicycle_is") else "Нет")
        st.metric("Тротуары", f"{int(jk.get('sidewalk_amount', 0))} м")

    with infra_col2:
        st.metric("Пандус", "Да" if jk.get("is_pandus") else "Нет")
        st.metric("Подъёмники МГН", int(jk.get("wheelchair_lift_amount", 0)))
        st.metric("Понижающие платформы",
                  "Да" if jk.get("step_down_platforms_is") else "Нет")

        # Мусорные площадки: отсутствие — плохо
        garbage = int(jk.get("garbage_area_amount", 0))
        if garbage == 0:
            st.metric("Мусорные площадки",
                      garbage,
                      delta="нет",
                      delta_color="inverse")
        else:
            st.metric("Мусорные площадки", garbage, delta="есть")

    st.markdown("---")

    # АРХИТЕКТУРА + ПЛОТНОСТЬ
    st.markdown("#### 📐 Архитектура и плотность")
    arch_col1, arch_col2 = st.columns(2)
    with arch_col1:
        # Высота потолков: < 2.7 плохо
        min_h = jk.get("min_ceiling_height", 0.0) or 0.0
        if min_h < 2.7:
            st.metric("Мин. высота потолков",
                      f"{min_h:.1f} м",
                      delta="ниже нормы 2.7",
                      delta_color="inverse")
        else:
            st.metric("Мин. высота потолков",
                      f"{min_h:.1f} м",
                      delta="норма ≥ 2.7")

        st.metric(
            "Этажность",
            f"{int(jk.get('min_floors', 0))}–{int(jk.get('max_floors', 0))}")

        # Плотность: > 6 кв/этаж плохо
        flats_pf = jk.get("avg_flats_on_floor", 0.0) or 0.0
        if flats_pf > 6:
            st.metric("Кв/этаж",
                      f"{flats_pf:.0f}",
                      delta="> 6 (высокая плотность)",
                      delta_color="inverse")
        else:
            st.metric("Кв/этаж", f"{flats_pf:.0f}", delta="≤ 6 (норма)")

    with arch_col2:
        # Площадь квартир: сильное отклонение от 60 м² — плохо
        avg_area = jk.get("avg_living_area_m2", 0.0) or 0.0
        if avg_area > 0 and abs(avg_area - 60) > 15:
            st.metric("Площадь квартир",
                      f"{avg_area:.0f} м²",
                      delta="сильно отклоняется от 60",
                      delta_color="inverse")
        else:
            st.metric("Площадь квартир",
                      f"{avg_area:.0f} м²",
                      delta="близко к 60 м²")

        # Нежилые: >10% — плохо
        non_res = jk.get("non_residential", 0.0) or 0.0
        if non_res > 0.10:
            st.metric("Нежилые (%)",
                      f"{non_res:.0%}",
                      delta="> 10%",
                      delta_color="inverse")
        else:
            st.metric("Нежилые (%)", f"{non_res:.0%}", delta="≤ 10%")

    st.markdown("---")
    st.subheader("📍 Инфраструктура рядом")
    if not df_infra.empty:
        current_infra = df_infra[df_infra["jk_name"] == selected_jk]
        if not current_infra.empty:
            infra_types = current_infra.groupby("type")["name"].apply(
                list).to_dict()
            for typ, names in infra_types.items():
                st.write(f"**{typ.title()}**: {', '.join(names[:3])}" +
                         (f" (+{len(names) - 3})" if len(names) > 3 else ""))
        else:
            st.write("📭 Нет данных об инфраструктуре рядом")
    else:
        st.write("📁 Загрузите infrastructure.xlsx")

elif mode == "Сравнение ЖК" and st.session_state.compare_applied and jk_a_data is not None and jk_b_data is not None:

    st.subheader(f"🆚 Сравнение: {jk_a} vs {jk_b}")

    # === ОСНОВНЫЕ МЕТРИКИ ===
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(f"### 🏢 {jk_a}")
        st.metric("ISD", f"{jk_a_data['isd']:.3f}")
        st.metric("Квартиры", int(jk_a_data["all_amount"]))
        st.metric("Студии %", f"{jk_a_data.get('studio_pct', 0):.0%}")
    with col_b:
        st.markdown(f"### 🏢 {jk_b}")
        st.metric("ISD", f"{jk_b_data['isd']:.3f}")
        st.metric("Квартиры", int(jk_b_data["all_amount"]))
        st.metric("Студии %", f"{jk_b_data.get('studio_pct', 0):.0%}")

    st.markdown("---")

    # === КОМПОНЕНТЫ ISD ===
    st.markdown("#### 📊 Компоненты ISD")
    comp_data = {
        "Компонент": [
            "🏠 Жилье (25%)", "🏗️ Комфорт (30%)", "🌳 Инфраструктура (25%)",
            "♿ Доступность (20%)"
        ],
        jk_a: [
            f"{jk_a_data.get('housing_score', 0):.3f}",
            f"{jk_a_data.get('comfort_score', 0):.3f}",
            f"{jk_a_data.get('infra_score', 0):.3f}",
            f"{jk_a_data.get('accessibility_score', 0):.3f}"
        ],
        jk_b: [
            f"{jk_b_data.get('housing_score', 0):.3f}",
            f"{jk_b_data.get('comfort_score', 0):.3f}",
            f"{jk_b_data.get('infra_score', 0):.3f}",
            f"{jk_b_data.get('accessibility_score', 0):.3f}"
        ]
    }
    st.dataframe(pd.DataFrame(comp_data), use_container_width=True)

    st.markdown("---")

    # === ДЕТАЛЬНОЕ СРАВНЕНИЕ С ЦВЕТАМИ ===
    st.markdown("#### 🔍 Детальное сравнение")

    # Студии
    studio_a = jk_a_data.get('studio_pct', 0)
    studio_b = jk_b_data.get('studio_pct', 0)
    col1, col2 = st.columns(2)
    with col1:
        if studio_a > 0.20:
            st.metric("Студии A",
                      f"{studio_a:.0%}",
                      delta=">20%",
                      delta_color="inverse")
        else:
            st.metric("Студии A", f"{studio_a:.0%}", "≤20%")
    with col2:
        if studio_b > 0.20:
            st.metric("Студии B",
                      f"{studio_b:.0%}",
                      delta=">20%",
                      delta_color="inverse")
        else:
            st.metric("Студии B", f"{studio_b:.0%}", "≤20%")

    if studio_a > studio_b:
        st.warning(
            f"⚠️ **{jk_a}**: больше студий ({studio_a:.0%} vs {studio_b:.0%})")
    elif studio_b > studio_a:
        st.warning(
            f"⚠️ **{jk_b}**: больше студий ({studio_b:.0%} vs {studio_a:.0%})")
    else:
        st.success("✅ **Студии**: равное количество")

    st.markdown("---")

    # Большие квартиры
    large_a = jk_a_data.get('large_flats_pct', 0)
    large_b = jk_b_data.get('large_flats_pct', 0)
    col1, col2 = st.columns(2)
    with col1:
        if large_a < 0.20:
            st.metric("Большие A",
                      f"{large_a:.0%}",
                      delta="<20%",
                      delta_color="inverse")
        else:
            st.metric("Большие A", f"{large_a:.0%}", "≥20%")
    with col2:
        if large_b < 0.20:
            st.metric("Большие B",
                      f"{large_b:.0%}",
                      delta="<20%",
                      delta_color="inverse")
        else:
            st.metric("Большие B", f"{large_b:.0%}", "≥20%")

    if large_a > large_b:
        st.success(
            f"✅ **{jk_a}**: больше семейного жилья ({large_a:.0%} vs {large_b:.0%})"
        )
    elif large_b > large_a:
        st.success(
            f"✅ **{jk_b}**: больше семейного жилья ({large_b:.0%} vs {large_a:.0%})"
        )
    else:
        st.info("ℹ️ **Семейное жилье**: равное количество")

    st.markdown("---")

    # Парковка
    park_a = jk_a_data.get('parking_raw', 0)
    park_b = jk_b_data.get('parking_raw', 0)
    col1, col2 = st.columns(2)
    with col1:
        if park_a < 1.0:
            st.metric("Парковка A",
                      f"{park_a:.0%}",
                      delta="<100%",
                      delta_color="inverse")
        else:
            st.metric("Парковка A", f"{park_a:.0%}", "≥100%")
    with col2:
        if park_b < 1.0:
            st.metric("Парковка B",
                      f"{park_b:.0%}",
                      delta="<100%",
                      delta_color="inverse")
        else:
            st.metric("Парковка B", f"{park_b:.0%}", "≥100%")

    if park_a > park_b:
        st.success(
            f"✅ **{jk_a}**: лучше парковка ({park_a:.0%} vs {park_b:.0%})")
    elif park_b > park_a:
        st.success(
            f"✅ **{jk_b}**: лучше парковка ({park_b:.0%} vs {park_a:.0%})")
    else:
        st.info("ℹ️ **Парковка**: одинаковая")

    st.markdown("---")

    # Архитектура
    ceiling_a = jk_a_data.get('min_ceiling_height', 0)
    ceiling_b = jk_b_data.get('min_ceiling_height', 0)
    col1, col2 = st.columns(2)
    with col1:
        if ceiling_a < 2.7:
            st.metric("Потолки A",
                      f"{ceiling_a:.1f}м",
                      delta="<2.7м",
                      delta_color="inverse")
        else:
            st.metric("Потолки A", f"{ceiling_a:.1f}м", "≥2.7м")
    with col2:
        if ceiling_b < 2.7:
            st.metric("Потолки B",
                      f"{ceiling_b:.1f}м",
                      delta="<2.7м",
                      delta_color="inverse")
        else:
            st.metric("Потолки B", f"{ceiling_b:.1f}м", "≥2.7м")

    floors_a = jk_a_data.get('max_floors', 0)
    floors_b = jk_b_data.get('max_floors', 0)
    if floors_a > floors_b:
        st.info(f"🏢 **{jk_a}**: выше ({floors_a} этажей vs {floors_b})")
    elif floors_b > floors_a:
        st.info(f"🏢 **{jk_b}**: выше ({floors_b} этажей vs {floors_a})")

    st.markdown("---")

    # === ИТОГОВЫЙ ВЕРДИКТ ===
    st.markdown("#### 🎯 Итоговый рейтинг")
    isd_diff = jk_b_data["isd"] - jk_a_data["isd"]

    col_win, col_lose = st.columns(2)
    if isd_diff > 0:
        # A лучше (меньше ISD)
        with col_win:
            st.markdown(f"### 🥇 **{jk_a}**")
            st.success(f"**ISD**: {jk_a_data['isd']:.3f} **(лидер)**")
            st.success("• Меньше студий")
            st.success("• Больше семейного жилья")
        with col_lose:
            st.markdown(f"### 🥈 **{jk_b}**")
            st.warning(f"**ISD**: {jk_b_data['isd']:.3f}")
    elif isd_diff < 0:
        # B лучше
        with col_win:
            st.markdown(f"### 🥇 **{jk_b}**")
            st.success(f"**ISD**: {jk_b_data['isd']:.3f} **(лидер)**")
            st.success("• Меньше студий")
            st.success("• Больше семейного жилья")
        with col_lose:
            st.markdown(f"### 🥈 **{jk_a}**")
            st.warning(f"**ISD**: {jk_a_data['isd']:.3f}")
    else:
        st.markdown("### 🤝 **Ничья!**")
        st.info(f"**ISD**: {jk_a_data['isd']:.3f} (равные по балансу)")

