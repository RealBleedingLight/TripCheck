import math
import requests
import polyline
import folium
from xml.etree.ElementTree import Element, SubElement, ElementTree
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

def get_route_and_waypoints(origin, destination):
    r = requests.get("https://maps.googleapis.com/maps/api/directions/json", params={
        "origin": origin,
        "destination": destination,
        "key": api_key
    }).json()

    if not r.get("routes"):
        raise ValueError(f"No route found. Status: {r.get('status')}")

    distance_km = r["routes"][0]["legs"][0]["distance"]["value"] / 1000
    duration_hr = r["routes"][0]["legs"][0]["duration"]["value"] / 3600
    polyline_encoded = r["routes"][0]["overview_polyline"]["points"]
    coords = polyline.decode(polyline_encoded)

    return polyline_encoded, coords, distance_km, duration_hr

def get_stop_points(coords, rest_km, fuel_km):
    total_distance = 0
    stop_points = []
    last_rest = 0
    last_fuel = 0

    for i in range(1, len(coords)):
        lat1, lon1 = coords[i - 1]
        lat2, lon2 = coords[i]
        segment = haversine(lat1, lon1, lat2, lon2)
        total_distance += segment

        if (total_distance - last_rest >= rest_km) or (total_distance - last_fuel >= fuel_km):
            stop_points.append({
                "coord": f"{lat2},{lon2}",
                "distance": round(total_distance, 2)
            })
            last_rest = total_distance
            last_fuel = total_distance

    return stop_points

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * \
        math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def get_fuel_stops(stop_points, mileage, avg_speed_kmph):
    stations = []
    last_distance = 0
    last_eta = 0

    for point in stop_points:
        coord = point["coord"]
        lat, lng = coord.split(",")
        distance_covered = point["distance"]

        r = requests.get("https://maps.googleapis.com/maps/api/place/nearbysearch/json", params={
            "location": coord,
            "radius": 5000,
            "type": "gas_station",
            "opennow": "true",
            "key": api_key
        }).json()

        filtered = [p for p in r.get("results", []) if p.get("rating", 0) >= 3.8]
        if not filtered:
            r = requests.get("https://maps.googleapis.com/maps/api/place/nearbysearch/json", params={
                "location": coord,
                "radius": 5000,
                "type": "gas_station",
                "key": api_key
            }).json()
            filtered = r.get("results", [])

        if filtered:
            top = filtered[0]
            eta_hr = distance_covered / avg_speed_kmph
            fuel_used = distance_covered / mileage

            stations.append({
                "name": top["name"],
                "address": top.get("vicinity", "Unknown"),
                "lat": top["geometry"]["location"]["lat"],
                "lng": top["geometry"]["location"]["lng"],
                "rating": top.get("rating"),
                "user_ratings_total": top.get("user_ratings_total", 0),
                "distance_km": round(distance_covered, 2),
                "eta_hr": round(eta_hr, 2),
                "fuel_used": round(fuel_used, 2),
                "distance_from_last": round(distance_covered - last_distance, 2),
                "fuel_from_last": round((distance_covered - last_distance) / mileage, 2),
                "time_from_last": round(eta_hr - last_eta, 2)
            })

            last_distance = distance_covered
            last_eta = eta_hr

    return stations

def draw_route_map(polyline_encoded, stations):
    coords = polyline.decode(polyline_encoded)
    m = folium.Map(location=coords[0], zoom_start=6)
    folium.PolyLine(coords, color="blue", weight=5).add_to(m)

    for stop in stations:
        folium.Marker(
            location=[stop['lat'], stop['lng']],
            popup=f"{stop['name']} ({stop.get('rating', 'N/A')}⭐)",
            icon=folium.Icon(color="red")
        ).add_to(m)

    m.save("templates/map.html")

def generate_gpx_file(stations, file_path="static/fuel_stops.gpx"):
    gpx = Element("gpx", version="1.1", creator="FuelStopPlanner")
    for stop in stations:
        wpt = SubElement(gpx, "wpt", lat=str(stop["lat"]), lon=str(stop["lng"]))
        name = SubElement(wpt, "name")
        name.text = stop["name"]
    ElementTree(gpx).write(file_path, encoding="utf-8", xml_declaration=True)
    return file_path


