import pytz
from datetime import datetime

# Current UTC time
utc_now = datetime.utcnow()

# Initialize an empty dictionary
timezone_dict = {}

# Populate the dictionary with timezone names and their UTC offsets in ±HH:MM format
for timezone_str in pytz.all_timezones:
    timezone = pytz.timezone(timezone_str)
    offset = timezone.utcoffset(utc_now)
    offset_hours = int(offset.total_seconds() // 3600)
    offset_minutes = int((offset.total_seconds() % 3600) // 60)

    # Format offset as ±HH:MM
    formatted_offset = f"{offset_hours:+03d}:{abs(offset_minutes):02d}"

    # Replace underscores with spaces in timezone names
    formatted_timezone_str = timezone_str
    
    # Add to dictionary
    timezone_dict[formatted_timezone_str] = formatted_offset
