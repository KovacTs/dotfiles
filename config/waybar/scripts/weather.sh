#!/usr/bin/env bash
set -euo pipefail

CACHE_FILE="/tmp/waybar-weather-cache.json"
LOCATION="${1:-${WEATHER_LOCATION:-}}"

wwo_icon() {
    local code="$1"
    case "$code" in
        113) echo "󰖙" ;; # Clear/Sunny
        116) echo "󰖕" ;; # Partly cloudy
        119|122) echo "󰖐" ;; # Cloudy/Overcast
        143|248|260) echo "󰖑" ;; # Fog/Mist
        176|263|266|293|296|353) echo "󰖗" ;; # Light rain/drizzle
        299|302|305|308|356|359) echo "󰖖" ;; # Rain/Heavy rain
        200|386|389|392|395) echo "󰖓" ;; # Thunder
        179|182|185|227|230|281|284|311|314|317|320|323|326|329|332|335|338|350|362|365|368|371|374|377) echo "󰖘" ;; # Snow/Sleet
        *) echo "󰖐" ;;
    esac
}

wmo_icon() {
    local code="$1"
    local is_day="${2:-1}"
    case "$code" in
        0)
            if [[ "$is_day" == "1" ]]; then echo "󰖙"; else echo "󰖔"; fi ;;
        1|2) echo "󰖕" ;;
        3) echo "󰖐" ;;
        45|48) echo "󰖑" ;;
        51|53|55|56|57|61|63|80|81) echo "󰖗" ;;
        65|66|67|82) echo "󰖖" ;;
        71|73|75|77|85|86) echo "󰖘" ;;
        95|96|99) echo "󰖓" ;;
        *) echo "󰖐" ;;
    esac
}

wmo_desc() {
    local code="$1"
    case "$code" in
        0) echo "Despejado" ;;
        1) echo "Mayormente despejado" ;;
        2) echo "Parcialmente nublado" ;;
        3) echo "Nublado" ;;
        45|48) echo "Niebla" ;;
        51|53|55) echo "Llovizna" ;;
        56|57) echo "Llovizna helada" ;;
        61|63) echo "Lluvia" ;;
        65) echo "Lluvia fuerte" ;;
        66|67) echo "Lluvia helada" ;;
        71|73|75|77) echo "Nieve" ;;
        80|81|82) echo "Chubascos" ;;
        85|86) echo "Chubascos de nieve" ;;
        95|96|99) echo "Tormenta eléctrica" ;;
        *) echo "Clima" ;;
    esac
}

fetch_wttr() {
    local url="https://wttr.in/${LOCATION}?format=j1&lang=es"
    local raw
    raw="$(curl -fsS --max-time 8 "$url" 2>/dev/null)" || return 1

    local temp feels hum code desc city
    temp="$(jq -r '.current_condition[0].temp_C // empty' <<<"$raw")" || return 1
    [[ -n "$temp" ]] || return 1
    feels="$(jq -r '.current_condition[0].FeelsLikeC // ""' <<<"$raw")"
    hum="$(jq -r '.current_condition[0].humidity // ""' <<<"$raw")"
    code="$(jq -r '.current_condition[0].weatherCode // "119"' <<<"$raw")"
    desc="$(jq -r '.current_condition[0].lang_es[0].value // .current_condition[0].weatherDesc[0].value // ""' <<<"$raw")"
    city="$(jq -r '.nearest_area[0].areaName[0].value // ""' <<<"$raw")"

    local icon
    icon="$(wwo_icon "$code")"
    local tooltip="${city:+${city}: }${desc}
Sensación: ${feels}°C | Humedad: ${hum}%"

    jq -cn --arg text "${icon} ${temp}°C" --arg tooltip "$tooltip" \
        '{text: $text, tooltip: $tooltip}'
}

fetch_open_meteo() {
    local geo lat lon city
    geo="$(curl -fsS --max-time 8 "https://ipwho.is/" 2>/dev/null)" || return 1
    lat="$(jq -r '.latitude // empty' <<<"$geo")" || return 1
    lon="$(jq -r '.longitude // empty' <<<"$geo")" || return 1
    [[ -n "$lat" && -n "$lon" ]] || return 1
    city="$(jq -r '.city // ""' <<<"$geo")"

    local raw
    raw="$(curl -fsS --max-time 8 "https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,is_day" 2>/dev/null)" || return 1

    local temp feels hum code is_day
    temp="$(jq -r '.current.temperature_2m // empty | round' <<<"$raw")" || return 1
    [[ -n "$temp" ]] || return 1
    feels="$(jq -r '.current.apparent_temperature // "" | round' <<<"$raw")"
    hum="$(jq -r '.current.relative_humidity_2m // ""' <<<"$raw")"
    code="$(jq -r '.current.weather_code // 3' <<<"$raw")"
    is_day="$(jq -r '.current.is_day // 1' <<<"$raw")"

    local icon desc
    icon="$(wmo_icon "$code" "$is_day")"
    desc="$(wmo_desc "$code")"
    local tooltip="${city:+${city}: }${desc}
Sensación: ${feels}°C | Humedad: ${hum}%"

    jq -cn --arg text "${icon} ${temp}°C" --arg tooltip "$tooltip" \
        '{text: $text, tooltip: $tooltip}'
}

if out="$(fetch_wttr)" || out="$(fetch_open_meteo)"; then
    printf '%s\n' "$out" > "$CACHE_FILE"
    printf '%s\n' "$out"
elif [[ -s "$CACHE_FILE" ]]; then
    cat "$CACHE_FILE"
else
    printf '{"text":"󰖐 --°C","tooltip":"Sin datos del clima"}\n'
fi
