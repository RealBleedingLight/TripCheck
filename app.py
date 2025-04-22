from flask import Flask, render_template, request, send_file
from utils import (
    get_route_and_waypoints,
    get_stop_points,
    get_fuel_stops,
    draw_route_map,
    generate_gpx_file
)
import os

app = Flask(__name__)

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/plan', methods=['POST'])
def plan():
    origin = request.form['origin']
    destination = request.form['destination']
    mileage = float(request.form['mileage'])
    fuel_capacity = float(request.form['fuel_capacity'])
    avg_speed = float(request.form['speed'])
    rest_interval = float(request.form['rest_interval'])

    rest_km = (avg_speed * rest_interval) / 60
    fuel_range_km = fuel_capacity * mileage

    try:
        polyline_data, coords, total_km, total_hr = get_route_and_waypoints(origin, destination)
        stop_points = get_stop_points(coords, rest_km, fuel_range_km)
        stations = get_fuel_stops(stop_points, mileage, avg_speed)

        gpx_path = generate_gpx_file(stations, file_path="static/fuel_stops.gpx")

        draw_route_map(polyline_data, stations)

        return render_template(
            "result.html",
            stations=stations,
            total_km=round(total_km, 1),
            total_hr=round(total_hr, 1),
            gpx_available=os.path.exists(gpx_path)
        )

    except Exception as e:
        return f"❌ Error: {e}", 500

@app.route('/download')
def download_gpx():
    gpx_path = "static/fuel_stops.gpx"
    if os.path.exists(gpx_path):
        return send_file(gpx_path, as_attachment=True)
    return "GPX file not found.", 404

if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
