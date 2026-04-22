import pandas as pd
import numpy as np
import os

def generate_synthetic_dataset(n_samples=100, seed=42):
    """
    Генерирует синтетический датасет ЖК Москвы с реалистичными зависимостями
    """
    rng = np.random.default_rng(seed)
    data = []
    
    for i in range(n_samples):
        # === БАЗОВЫЕ ПАРАМЕТРЫ ===
        all_amount = int(rng.lognormal(mean=6.5, sigma=0.8))
        all_amount = np.clip(all_amount, 100, 2500)
        
        max_floors = int(rng.choice(
            [5, 8, 10, 12, 14, 16, 18, 20, 22, 25, 30, 35, 40],
            p=[0.02, 0.05, 0.10, 0.15, 0.15, 0.12, 0.10, 0.10, 0.08, 0.06, 0.04, 0.02, 0.01]
        ))
        min_floors = max(1, max_floors - int(rng.integers(0, 3)))
        
        # === РАСПРЕДЕЛЕНИЕ КВАРТИР ===
        studio_pct_target = rng.beta(1.5, 4) * 0.5
        studio_amount = int(all_amount * studio_pct_target)
        
        one_room_amount = int(all_amount * rng.uniform(0.25, 0.50))
        two_room_amount = int(all_amount * rng.uniform(0.20, 0.40))
        three_room_amount = int(all_amount * rng.uniform(0.10, 0.30))
        four_plus_amount = int(all_amount * rng.uniform(0.02, 0.15))
        
        total_rooms = studio_amount + one_room_amount + two_room_amount + three_room_amount + four_plus_amount
        if total_rooms != all_amount and total_rooms > 0:
            two_room_amount += (all_amount - total_rooms)
            two_room_amount = max(0, two_room_amount)
        
        # === ПАРАМЕТРЫ КОМФОРТА ===
        if rng.random() < 0.3:
            avg_living_area = rng.uniform(35, 50)
            min_ceiling_height = rng.uniform(2.6, 2.75)
        elif rng.random() < 0.6:
            avg_living_area = rng.uniform(50, 70)
            min_ceiling_height = rng.uniform(2.75, 2.95)
        else:
            avg_living_area = rng.uniform(70, 120)
            min_ceiling_height = rng.uniform(2.95, 3.3)
        
        max_ceiling_height = min_ceiling_height + rng.uniform(0.2, 0.5)
        living_area_m2 = avg_living_area * all_amount
        
        if max_floors <= 10:
            avg_flats_on_floor = int(rng.uniform(3, 6))
        elif max_floors <= 20:
            avg_flats_on_floor = int(rng.uniform(5, 9))
        else:
            avg_flats_on_floor = int(rng.uniform(7, 12))
        
        # === ПАРКОВКА ===
        if avg_living_area < 50:
            percent_of_parking = rng.uniform(0.3, 0.8) * 100
        elif avg_living_area < 75:
            percent_of_parking = rng.uniform(0.6, 1.2) * 100
        else:
            percent_of_parking = rng.uniform(1.0, 1.8) * 100
        
        places_for_cars_in_parking = int(all_amount * (percent_of_parking / 100))
        guest_places_for_cars_on_territory = int(places_for_cars_in_parking * rng.uniform(0.05, 0.15))
        guest_places_for_cars_near_territory = int(places_for_cars_in_parking * rng.uniform(0, 0.1))
        
        # === ИНФРАСТРУКТУРА ===
        children_playing_zone_amount = max(1, int(all_amount / rng.integers(250, 450)))
        
        if all_amount < 300:
            sports_amount = int(rng.choice([0, 1, 2], p=[0.4, 0.4, 0.2]))
        elif all_amount < 800:
            sports_amount = int(rng.choice([1, 2, 3], p=[0.3, 0.5, 0.2]))
        else:
            sports_amount = int(rng.choice([2, 3, 4, 5], p=[0.2, 0.4, 0.3, 0.1]))
        
        bicycle_is = int(rng.choice([0, 1], p=[0.55, 0.45]))
        sidewalk_amount = int(rng.integers(1, 5)) if rng.random() > 0.1 else 0
        garbage_area_amount = max(1, int(all_amount / rng.integers(150, 300)))
        
        # === ЛИФТЫ И ПОДЪЕЗДЫ ===
        if all_amount < 300:
            entrances_amount = int(rng.integers(1, 4))
        elif all_amount < 800:
            entrances_amount = int(rng.integers(3, 7))
        else:
            entrances_amount = int(rng.integers(5, 12))
        
        if max_floors <= 5:
            elevators_amount = 0
            elevators_on_entrance = 0
        elif max_floors <= 10:
            elevators_amount = entrances_amount * int(rng.integers(1, 2))
            elevators_on_entrance = elevators_amount / entrances_amount if entrances_amount > 0 else 0
        else:
            elevators_amount = entrances_amount * int(rng.integers(2, 4))
            elevators_on_entrance = elevators_amount / entrances_amount if entrances_amount > 0 else 0
        
        # === ДОСТУПНОСТЬ ===
        is_pandus = int(rng.choice([0, 1], p=[0.25, 0.75]))
        step_down_platforms_is = int(rng.choice([0, 1], p=[0.4, 0.6]))
        wheelchair_lift_amount = int(rng.choice([0, 1, 2], p=[0.5, 0.35, 0.15])) if max_floors > 5 else 0
        
        # === НЕЖИЛЫЕ ===
        not_living_amount = int(all_amount * rng.uniform(0.02, 0.12))
        amount_other_not_living = int(not_living_amount * rng.uniform(0.3, 0.7))
        
        # === КООРДИНАТЫ ===
        if rng.random() < 0.4:
            latitude = rng.uniform(55.65, 55.85)
            longitude = rng.uniform(37.45, 37.75)
        else:
            latitude = rng.uniform(55.5, 56.0)
            longitude = rng.uniform(37.2, 37.9)
        
        # === РАСЧЕТ ЦЕЛЕВОЙ ПЕРЕМЕННОЙ (ISD) ===
        studio_ratio = studio_amount / all_amount if all_amount > 0 else 0
        large_flats_ratio = (three_room_amount + four_plus_amount) / all_amount if all_amount > 0 else 0
        area_deviation = abs(avg_living_area - 60) / 60
        non_residential_ratio = not_living_amount / all_amount if all_amount > 0 else 0
        
        housing_score = (
            0.4 * np.clip(studio_ratio / 0.25, 0, 1) +
            0.3 * (1 - np.clip(large_flats_ratio / 0.25, 0, 1)) +
            0.2 * np.clip(area_deviation, 0, 1) +
            0.1 * np.clip(non_residential_ratio / 0.1, 0, 1)
        )
        
        parking_ratio = percent_of_parking / 100
        parking_deficit = (1 - parking_ratio) if parking_ratio < 1 else 0
        ceiling_penalty = (2.7 - min_ceiling_height) / 0.5 if min_ceiling_height < 2.7 else 0
        floors_penalty = (max_floors - 25) / 15 if max_floors > 25 else 0
        elevator_penalty = (2 - elevators_on_entrance) / 2 if elevators_on_entrance < 2 else 0
        
        comfort_score = (
            0.25 * np.clip(avg_flats_on_floor / 8, 0, 1) +
            0.25 * np.clip(parking_deficit, 0, 1) +
            0.15 * np.clip(ceiling_penalty, 0, 1) +
            0.20 * np.clip(floors_penalty, 0, 1) +
            0.15 * np.clip(elevator_penalty, 0, 1)
        )
        
        children_norm = children_playing_zone_amount / (all_amount / 300) if all_amount > 0 else 0
        infra_score = (
            0.25 * (1 - np.clip(children_norm, 0, 1)) +
            0.15 * (1 if sports_amount == 0 else 0) +
            0.10 * (1 - bicycle_is) +
            0.10 * (1 if sidewalk_amount == 0 else 0) +
            0.20 * (1 if garbage_area_amount == 0 else 0) +
            0.20 * (1 if (max_floors > 5 and elevators_amount == 0) else 0)
        )
        
        accessibility_sum = is_pandus + step_down_platforms_is + (1 if wheelchair_lift_amount > 0 else 0)
        accessibility_score = (3 - accessibility_sum) / 3
        
        isd_target = (
            0.25 * housing_score +
            0.30 * comfort_score +
            0.25 * infra_score +
            0.20 * accessibility_score +
            rng.normal(0, 0.03)
        )
        isd_target = np.clip(isd_target, 0, 1)
        
        row = {
            'name': f'ЖК_Синтетика_{i+1:03d}',
            'all_amount': all_amount,
            'studio_amount': studio_amount,
            '1_room_amount': one_room_amount,
            '2_room_amount': two_room_amount,
            '3_room_amount': three_room_amount,
            '4+_room_amount': four_plus_amount,
            'avg_flats_on_floor': avg_flats_on_floor,
            'not_living_amount': not_living_amount,
            'places_for_cars_in_parking': places_for_cars_in_parking,
            'guest_places_for_cars_on_territory': guest_places_for_cars_on_territory,
            'guest_places_for_cars_near_territory': guest_places_for_cars_near_territory,
            'percent_of_parking': f"{percent_of_parking:.2f}%",
            'amount_other_not_living': amount_other_not_living,
            'living_area_m2': int(living_area_m2),
            'avg_living_area_m2': round(avg_living_area, 1),
            'min_ceiling_height': round(min_ceiling_height, 2),
            'max_ceiling_height': round(max_ceiling_height, 2),
            'min_floors': min_floors,
            'max_floors': max_floors,
            'elevators_amount': elevators_amount,
            'entrances_amount': entrances_amount,
            'elevators_on_entracne': round(elevators_on_entrance, 3),
            'children_playing_zone_amount': children_playing_zone_amount,
            'sports_amount': sports_amount,
            'bicycle_is': bicycle_is,
            'sidewalk_amount': sidewalk_amount,
            'garbage_area_amount': garbage_area_amount,
            'step_down_platforms_is': step_down_platforms_is,
            'is_pandus': is_pandus,
            'wheelchair_lift_amount': wheelchair_lift_amount,
            'latitude': round(latitude, 6),
            'longitude': round(longitude, 6),
            'target_isd': round(isd_target, 3),
            'housing_score': round(housing_score, 3),
            'comfort_score': round(comfort_score, 3),
            'infra_score': round(infra_score, 3),
            'accessibility_score': round(accessibility_score, 3)
        }
        data.append(row)
    
    return pd.DataFrame(data)


if __name__ == "__main__":
    print("Генерация синтетического датасета...")
    df = generate_synthetic_dataset(n_samples=100, seed=42)
    
    os.makedirs('data', exist_ok=True)
    output_file = 'data/synthetic_jk_train.xlsx'
    df.to_excel(output_file, index=False)
    
    print(f"✅ Сгенерировано {len(df)} записей")
    print(f"📊 Диапазон ISD: {df['target_isd'].min():.3f} – {df['target_isd'].max():.3f}")
    print(f"📈 Средний ISD: {df['target_isd'].mean():.3f}")
    print(f"\n📁 Файл сохранен: {output_file}")