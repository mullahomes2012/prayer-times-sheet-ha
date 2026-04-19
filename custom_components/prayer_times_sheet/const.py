DOMAIN = "prayer_times_sheet"

CONF_SHEET_URL = "sheet_url"
CONF_SHEET_NAME = "sheet_name"
CONF_SHEET_PREFIX = "sheet_prefix"
CONF_DATE_COLUMN = "date_column"
CONF_DATE_FORMAT = "date_format"
CONF_COLUMN_MAPPING = "column_mapping"
CONF_ENABLED_PRAYERS = "enabled_prayers"
CONF_CUSTOM_NAMES = "custom_names"
CONF_END_TIMES = "end_times"

SCAN_INTERVAL_MINUTES = 60

# End time modes
END_TIME_NONE = "none"
END_TIME_MINUTES = "minutes"
END_TIME_PRAYER = "prayer"

# The canonical list of prayer/time slots the integration understands.
# Each entry: (key, friendly label)
PRAYER_SLOTS = [
    ("fajr_start",      "Fajr Start"),
    ("fajr_jamaat",     "Fajr Jama'ah"),
    ("sunrise",         "Sunrise"),
    ("dhuhr_start",     "Dhuhr Start"),
    ("dhuhr_jamaat",    "Dhuhr Jama'ah"),
    ("zawaal",          "Zawaal"),
    ("asr_start",       "Asr Start"),
    ("asr_jamaat",      "Asr Jama'ah"),
    ("maghrib_start",   "Maghrib Start"),
    ("maghrib_jamaat",  "Maghrib Jama'ah"),
    ("isha_start",      "Isha Start"),
    ("isha_jamaat",     "Isha Jama'ah"),
    ("jumuah",          "Jumu'ah"),
    ("suhoor",          "Suhoor"),
    ("iftaar",          "Iftaar"),
]

PRAYER_SLOT_KEYS = [k for k, _ in PRAYER_SLOTS]
PRAYER_SLOT_LABELS = {k: v for k, v in PRAYER_SLOTS}

# Default end time pairings: prayer_key -> (mode, value)
# mode = END_TIME_PRAYER: value is another prayer key
# mode = END_TIME_MINUTES: value is number of minutes (as string)
DEFAULT_END_TIMES: dict[str, tuple[str, str]] = {
    "fajr_start":     (END_TIME_PRAYER,  "sunrise"),
    "fajr_jamaat":    (END_TIME_PRAYER,  "sunrise"),
    "sunrise":        (END_TIME_MINUTES, "15"),
    "zawaal":         (END_TIME_PRAYER,  "dhuhr_start"),
    "dhuhr_start":    (END_TIME_PRAYER,  "asr_start"),
    "dhuhr_jamaat":   (END_TIME_PRAYER,  "asr_start"),
    "asr_start":      (END_TIME_PRAYER,  "maghrib_start"),
    "asr_jamaat":     (END_TIME_PRAYER,  "maghrib_start"),
    "maghrib_start":  (END_TIME_PRAYER,  "isha_start"),
    "maghrib_jamaat": (END_TIME_PRAYER,  "isha_start"),
    "isha_start":     (END_TIME_PRAYER,  "fajr_start"),
    "isha_jamaat":    (END_TIME_PRAYER,  "fajr_start"),
    "jumuah":         (END_TIME_PRAYER,  "asr_start"),
    "suhoor":         (END_TIME_PRAYER,  "fajr_start"),
    "iftaar":         (END_TIME_PRAYER,  "maghrib_start"),
}
