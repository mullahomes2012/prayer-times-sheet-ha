DOMAIN = "prayer_times_sheet"

CONF_SHEET_URL = "sheet_url"
CONF_SHEET_NAME = "sheet_name"
CONF_DATE_COLUMN = "date_column"
CONF_DATE_FORMAT = "date_format"
CONF_COLUMN_MAPPING = "column_mapping"
CONF_ENABLED_PRAYERS = "enabled_prayers"
CONF_CUSTOM_NAMES = "custom_names"

SCAN_INTERVAL_MINUTES = 60

# The canonical list of prayer/time slots the integration understands.
# Each entry: (key, friendly label)
PRAYER_SLOTS = [
    ("fajr_start",      "Fajr Start"),
    ("fajr_jamaat",     "Fajr Jamaat"),
    ("sunrise",         "Sunrise"),
    ("dhuhr_start",     "Dhuhr Start"),
    ("dhuhr_jamaat",    "Dhuhr Jamaat"),
    ("zawaal",          "Zawaal"),
    ("asr_start",       "Asr Start"),
    ("asr_jamaat",      "Asr Jamaat"),
    ("maghrib_start",   "Maghrib Start"),
    ("maghrib_jamaat",  "Maghrib Jamaat"),
    ("isha_start",      "Isha Start"),
    ("isha_jamaat",     "Isha Jamaat"),
    ("jumuah",          "Jumuah"),
    ("suhoor",          "Suhoor"),
    ("iftaar",          "Iftaar"),
]

PRAYER_SLOT_KEYS = [k for k, _ in PRAYER_SLOTS]
PRAYER_SLOT_LABELS = {k: v for k, v in PRAYER_SLOTS}
