# Prayer Times (Google Sheet) — Home Assistant Integration

A custom Home Assistant integration that reads daily prayer times from a publicly published Google Sheet and creates individual time sensors for each prayer — one device per sheet, fully configurable through the UI.

## Features

- ✅ Set up entirely through the HA UI — no YAML required
- ✅ Add multiple sheets (e.g. one for Jamaa'ah times, one for start times, or multiple masjids)
- ✅ Map your sheet's columns to the correct prayer slots
- ✅ Choose exactly which prayers to create sensors for
- ✅ Change enabled prayers at any time via Options
- ✅ Refreshes automatically every hour
- ✅ One device per sheet in the HA device registry

## Installation via HACS

1. In HACS, go to **Integrations → Custom repositories**
2. Add your repository URL and set category to **Integration**
3. Find **Prayer Times (Google Sheet)** and install
4. Restart Home Assistant

## Manual Installation

1. Copy the `custom_components/prayer_times_sheet` folder into your HA `custom_components` directory
2. Restart Home Assistant

## Setup

### 1. Publish your Google Sheet

In Google Sheets: **File → Share → Publish to web → Sheet1 → CSV → Publish**

Copy the URL — it will look like:
```
https://docs.google.com/spreadsheets/d/e/XXXX/pub?gid=0&single=true&output=csv
```

### 2. Add the integration

Go to **Settings → Devices & Services → Add Integration → Prayer Times (Google Sheet)**

You will be guided through 4 steps:

| Step | What you do |
|------|-------------|
| 1 | Paste your sheet URL, give it a name, choose the date format |
| 2 | Select which column contains the date |
| 3 | Map each prayer slot to its column in your sheet |
| 4 | Choose which prayers to create HA sensors for |

### 3. Use the sensors in automations

Each enabled prayer becomes a sensor, e.g.:

- `sensor.my_masjid_dhuhr_jamaat` → `13:30`
- `sensor.my_masjid_maghrib_start` → `20:14`

Use them in automations with a **Template trigger**:

```yaml
trigger:
  - platform: template
    value_template: >
      {{ now().strftime('%H:%M') == states('sensor.my_masjid_dhuhr_jamaat') }}
```

## Supported Prayer Slots

| Key | Label |
|-----|-------|
| `fajr_start` | Fajr Start |
| `fajr_jamaat` | Fajr Jamaat |
| `sunrise` | Sunrise |
| `dhuhr_start` | Dhuhr Start |
| `dhuhr_jamaat` | Dhuhr Jamaat |
| `zawaal` | Zawaal |
| `asr_start` | Asr Start |
| `asr_jamaat` | Asr Jamaat |
| `maghrib_start` | Maghrib Start |
| `maghrib_jamaat` | Maghrib Jamaat |
| `isha_start` | Isha Start |
| `isha_jamaat` | Isha Jamaat |
| `jumuah` | Jumuah |
| `suhoor` | Suhoor |
| `iftaar` | Iftaar |

## Date Format Reference

| Format string | Example |
|---------------|---------|
| `%-d/%-m/%Y`  | 19/4/2026 |
| `%d/%m/%Y`    | 19/04/2026 |
| `%Y-%m-%d`    | 2026-04-19 |
| `%d-%m-%Y`    | 19-04-2026 |
| `%d %b %Y`    | 19 Apr 2026 |
| `%d %B %Y`    | 19 April 2026 |

## Troubleshooting

**Sensors show `unavailable`**
- Check the sheet is published to the web as CSV
- Verify the date format matches your sheet exactly
- Check HA logs for `prayer_times_sheet` errors

**Wrong time showing**
- Check the column mapping in the integration options
- Ensure the sheet has a row for today's date
