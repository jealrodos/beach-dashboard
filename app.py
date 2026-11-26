import os
from configuration import load_beaches
from flask import Flask, jsonify, render_template
import requests
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time


app = Flask(__name__)


# ============================================================
# BEACHES
# ============================================================

BEACHES = load_beaches()


# ============================================================
# SETTINGS
# ============================================================

CACHE_SECONDS = int(os.environ.get("CACHE_SECONDS", "60"))

cache = {
    "data": None,
    "timestamp": 0,
}

cache_lock = threading.Lock()


# ============================================================
# TIDE
# ============================================================

def get_tide_events():
    """
    Get Porto/Foz tide predictions from TideCheck.

    TideCheck uses the Porto harmonic reference station
    for Foz do Douro.
    """

    url = "https://tidecheck.com/tides/foz-do-douro"

    response = requests.get(
        url,
        timeout=10,
        headers={
            "User-Agent": "BeachDashboard/1.0",
        },
    )

    response.raise_for_status()

    html = response.text

    # Remove HTML tags.
    text = re.sub(
        r"<[^>]+>",
        " ",
        html,
    )

    # Decode common HTML entities.
    text = (
        text
        .replace("&nbsp;", " ")
        .replace("&amp;", "&")
    )

    # Collapse whitespace.
    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    pattern = re.compile(
        r"(High|Low)\s+Tide\s+"
        r"(\d{1,2}:\d{2}\s*(?:AM|PM))\s+"
        r"([0-9]+(?:\.[0-9]+)?)m",
        re.IGNORECASE,
    )

    matches = pattern.findall(text)

    if not matches:
        raise ValueError(
            "No tide events found"
        )

    timezone = ZoneInfo(
        "Europe/Lisbon"
    )

    now = datetime.now(
        timezone
    )

    events = []

    for index, (
        tide_type,
        time_string,
        height,
    ) in enumerate(matches):

        day_offset = index // 4

        event_date = (
            now.date()
            + timedelta(days=day_offset)
        )

        parsed_time = datetime.strptime(
            time_string.strip().upper(),
            "%I:%M %p",
        ).time()

        event_time = datetime.combine(
            event_date,
            parsed_time,
            tzinfo=timezone,
        )

        events.append(
            {
                "type": tide_type.lower(),
                "time": event_time.isoformat(),
                "height": float(height),
            }
        )

    future_events = [
        event
        for event in events
        if datetime.fromisoformat(
            event["time"]
        ) > now
    ]

    future_events.sort(
        key=lambda event: event["time"]
    )

    return future_events[:2]


def get_current_tide(next_event):
    """
    Determine tidal direction from the next predicted extreme.

    Next high tide -> rising
    Next low tide  -> falling
    """

    if not next_event:

        return {
            "state": "unknown",
            "state_icon": "—",
        }

    if next_event["type"] == "high":

        return {
            "state": "rising",
            "state_icon": "↗",
        }

    return {
        "state": "falling",
        "state_icon": "↘",
    }


def get_tide():

    try:

        events = get_tide_events()

        next_event = (
            events[0]
            if len(events) > 0
            else None
        )

        following_event = (
            events[1]
            if len(events) > 1
            else None
        )

        current = get_current_tide(
            next_event
        )

        return {
            "location": "Porto / Foz",

            "state": current["state"],

            "state_icon": current[
                "state_icon"
            ],

            "next": next_event,

            "following": following_event,
        }

    except Exception as error:

        print(
            f"Tide error: {error}"
        )

        return {
            "location": "Porto / Foz",

            "state": "unavailable",

            "state_icon": "—",

            "next": None,

            "following": None,

            "error": str(error),
        }


# ============================================================
# WEATHER
# ============================================================

def get_all_weather():
    """
    Get current weather for all beach locations
    in ONE Open-Meteo request.

    This avoids making nine simultaneous requests
    and hitting Open-Meteo rate limits.
    """

    params = {
        "latitude": ",".join(
            str(beach["lat"])
            for beach in BEACHES
        ),
        "longitude": ",".join(
            str(beach["lon"])
            for beach in BEACHES
        ),
        "current": (
            "temperature_2m,"
            "relative_humidity_2m,"
            "apparent_temperature,"
            "precipitation,"
            "weather_code,"
            "wind_speed_10m,"
            "wind_direction_10m"
        ),
        "timezone": "Europe/Lisbon",
    }

    response = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params=params,
        timeout=15,
    )

    response.raise_for_status()

    data = response.json()

    if not isinstance(data, list):
        data = [data]

    weather = [
        item.get(
            "current",
            {},
        )
        for item in data
    ]

    if len(weather) != len(BEACHES):

        raise ValueError(
            "Open-Meteo returned "
            f"{len(weather)} locations, "
            f"expected {len(BEACHES)}"
        )

    return weather


# ============================================================
# MARINE
# ============================================================

def get_marine(beach):

    params = {
        "latitude": beach["lat"],
        "longitude": beach["lon"],
        "current": (
            "wave_height,"
            "wave_direction,"
            "sea_surface_temperature"
        ),
        "timezone": "Europe/Lisbon",
    }

    response = requests.get(
        "https://marine-api.open-meteo.com/v1/marine",
        params=params,
        timeout=10,
    )

    response.raise_for_status()

    data = response.json()

    return data.get(
        "current",
        {},
    )


# ============================================================
# SPECIAL WATER TEMPERATURES
# ============================================================

def get_douro_temperature():
    """
    Live Porto/Douro water temperature.

    Source: SeaTemperature Porto / Douro.
    """

    url = (
        "https://pt.seatemperature.net/"
        "current/portugal/"
        "water-temp-in-porto-in-douro"
    )

    response = requests.get(
        url,
        timeout=10,
        headers={
            "User-Agent": "BeachDashboard/1.0",
        },
    )

    response.raise_for_status()

    html = response.text

    text = re.sub(
        r"<[^>]+>",
        " ",
        html,
    )

    text = (
        text
        .replace("&nbsp;", " ")
        .replace("&amp;", "&")
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    matches = re.findall(
        r"Temperatura atual da água"
        r".{0,200}?"
        r"(\d+(?:[.,]\d+)?)\s*°C",
        text,
        re.IGNORECASE,
    )

    if not matches:

        matches = re.findall(
            r"Current Water Temperature"
            r".{0,200}?"
            r"(\d+(?:[.,]\d+)?)\s*°C",
            text,
            re.IGNORECASE,
        )

    if not matches:

        matches = re.findall(
            r"(\d+(?:[.,]\d+)?)\s*°C",
            text,
        )

    if not matches:

        raise ValueError(
            "Douro water temperature not found"
        )

    for value in matches:

        temperature = float(
            value.replace(",", ".")
        )

        if 5 <= temperature <= 30:

            return {
                "value": round(
                    temperature,
                    1,
                ),
                "source": "Porto / Douro",
            }

    raise ValueError(
        "No realistic Douro temperature found"
    )


def get_azibo_temperature():
    """
    Live Barragem de Azibo water temperature.

    Source: SeaTemperature.net
    """

    url = (
        "https://pt.seatemperature.net/"
        "lagos/water-temp-in-albufeira-da-barragem-do-azibo"
    )

    response = requests.get(
        url,
        timeout=10,
        headers={
            "User-Agent": "BeachDashboard/1.0",
        },
    )

    response.raise_for_status()

    html = response.text

    text = re.sub(
        r"<[^>]+>",
        " ",
        html,
    )

    text = (
        text
        .replace("&nbsp;", " ")
        .replace("&amp;", "&")
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    matches = re.findall(
        r"Temperatura atual da água"
        r".{0,200}?"
        r"(\d+(?:[.,]\d+)?)\s*°C",
        text,
        re.IGNORECASE,
    )

    if not matches:

        matches = re.findall(
            r"Current Water Temperature"
            r".{0,200}?"
            r"(\d+(?:[.,]\d+)?)\s*°C",
            text,
            re.IGNORECASE,
        )

    if not matches:

        raise ValueError(
            "Azibo water temperature not found"
        )

    temperature = float(
        matches[0].replace(",", ".")
    )

    if not 5 <= temperature <= 30:

        raise ValueError(
            f"Unrealistic Azibo temperature: "
            f"{temperature}°C"
        )

    return {
        "value": round(
            temperature,
            1,
        ),
        "source": "Barragem de Azibo",
    }


def get_limens_temperature():
    """
    Current Praia de Liméns water temperature
    from AEMET.
    """

    url = (
        "https://www.aemet.es/en/eltiempo/"
        "prediccion/playas/"
        "limens-3600807"
    )

    response = requests.get(
        url,
        timeout=10,
        headers={
            "User-Agent": "Mozilla/5.0 "
                          "(BeachDashboard/1.0)",
        },
    )

    response.raise_for_status()

    html = response.text

    # --------------------------------------------------------
    # Normalize HTML entities
    # --------------------------------------------------------

    html = (
        html
        .replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&deg;", "°")
        .replace("&#176;", "°")
        .replace("&#xB0;", "°")
        .replace("&#xB0;", "°")
    )

    # --------------------------------------------------------
    # First try the English label directly in the HTML.
    #
    # AEMET currently presents:
    #
    # Water temperature (°C)
    # 18
    # --------------------------------------------------------

    pattern = re.compile(
        r"Water\s+temperature"
        r".{0,500}?"
        r"\(\s*°?\s*C\s*\)"
        r".{0,500}?"
        r"(\d+(?:[.,]\d+)?)",
        re.IGNORECASE | re.DOTALL,
    )

    matches = pattern.findall(
        html
    )

    # --------------------------------------------------------
    # Spanish fallback
    # --------------------------------------------------------

    if not matches:

        pattern = re.compile(
            r"Temperatura\s+del\s+agua"
            r".{0,500}?"
            r"\(\s*°?\s*C\s*\)"
            r".{0,500}?"
            r"(\d+(?:[.,]\d+)?)",
            re.IGNORECASE | re.DOTALL,
        )

        matches = pattern.findall(
            html
        )

    # --------------------------------------------------------
    # If the HTML structure changes again, use the rendered
    # text version as a fallback.
    # --------------------------------------------------------

    if not matches:

        text = re.sub(
            r"<[^>]+>",
            " ",
            html,
        )

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        pattern = re.compile(
            r"Water\s+temperature"
            r".{0,100}?"
            r"(\d+(?:[.,]\d+)?)",
            re.IGNORECASE,
        )

        matches = pattern.findall(
            text
        )

    # --------------------------------------------------------
    # Final Spanish fallback
    # --------------------------------------------------------

    if not matches:

        text = re.sub(
            r"<[^>]+>",
            " ",
            html,
        )

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        pattern = re.compile(
            r"Temperatura\s+del\s+agua"
            r".{0,100}?"
            r"(\d+(?:[.,]\d+)?)",
            re.IGNORECASE,
        )

        matches = pattern.findall(
            text
        )

    if not matches:

        raise ValueError(
            "Liméns water temperature not found"
        )

    # --------------------------------------------------------
    # Pick the first realistic temperature.
    # --------------------------------------------------------

    for value in matches:

        try:

            temperature = float(
                value.replace(",", ".")
            )

        except ValueError:

            continue

        if 5 <= temperature <= 30:

            return {
                "value": round(
                    temperature,
                    1,
                ),
                "source": "AEMET Liméns",
            }

    raise ValueError(
        "No realistic Liméns temperature found"
    )

# ============================================================
# BUILD BEACH DATA
# ============================================================

def get_beach_data(
    beach,
    weather,
):

    result = {
        **beach,
        "weather": weather,
    }

    # --------------------------------------------------------
    # ATLANTIC / SEA
    # --------------------------------------------------------

    if beach["type"] == "sea":

        result["marine"] = get_marine(
            beach
        )

    # --------------------------------------------------------
    # DOURO
    # --------------------------------------------------------

    elif beach["type"] == "douro":

        result["water_temperature"] = (
            get_douro_temperature()
        )

    # --------------------------------------------------------
    # AZIBO
    # --------------------------------------------------------

    elif beach["type"] == "lake":

        result["water_temperature"] = (
            get_azibo_temperature()
        )

    # --------------------------------------------------------
    # LIMÉNS
    # --------------------------------------------------------

    elif beach["type"] == "limens":

        result["water_temperature"] = (
            get_limens_temperature()
        )

    return result


# ============================================================
# BUILD COMPLETE DASHBOARD
# ============================================================

def build_dashboard():

    results = []

    # --------------------------------------------------------
    # WEATHER
    # --------------------------------------------------------

    weather_data = get_all_weather()

    # --------------------------------------------------------
    # OTHER DATA
    # --------------------------------------------------------

    with ThreadPoolExecutor(
        max_workers=len(BEACHES)
    ) as executor:

        future_map = {}

        for index, beach in enumerate(
            BEACHES
        ):

            future = executor.submit(
                get_beach_data,
                beach,
                weather_data[index],
            )

            future_map[future] = beach

        completed = {}

        for future in as_completed(
            future_map
        ):

            beach = future_map[future]

            try:

                completed[
                    beach["name"]
                ] = future.result()

            except Exception as error:

                print(
                    f"Beach error "
                    f"{beach['name']}: {error}"
                )

                completed[
                    beach["name"]
                ] = {
                    **beach,
                    "weather": weather_data[
                        BEACHES.index(beach)
                    ],
                    "error": str(error),
                }

    # --------------------------------------------------------
    # RESTORE DEFINED BEACH ORDER
    # --------------------------------------------------------

    for beach in BEACHES:

        results.append(
            completed[
                beach["name"]
            ]
        )

    return {
        "tide": get_tide(),
        "beaches": results,
    }


# ============================================================
# API
# ============================================================

@app.route("/")
def index():

    return render_template(
        "index.html", home_url=os.environ.get("HOME_URL", "/")
    )


@app.route("/health")
def health():

    return jsonify(
        status="ok", revision=os.environ.get("ATRIA_GIT_SHA", "untracked")
    )


@app.route("/api/beaches")
def beaches():

    now = time.time()

    # --------------------------------------------------------
    # RETURN CACHED DATA WHEN STILL FRESH
    # --------------------------------------------------------

    with cache_lock:

        if (
            cache["data"] is not None
            and now - cache["timestamp"]
            < CACHE_SECONDS
        ):

            return jsonify(
                cache["data"]
            )

    # --------------------------------------------------------
    # BUILD FRESH DATA
    # --------------------------------------------------------

    try:

        data = build_dashboard()

    except Exception as error:

        print(
            f"Dashboard error: {error}"
        )

        return jsonify(
            {
                "error": str(error)
            }
        ), 500

    # --------------------------------------------------------
    # STORE IN CACHE
    # --------------------------------------------------------

    with cache_lock:

        cache["data"] = data
        cache["timestamp"] = time.time()

    return jsonify(data)


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=8000,
    )
