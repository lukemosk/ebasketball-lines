from datetime import datetime, timedelta, timezone
def quarter_end_times(start_utc_str:str):
    t0 = datetime.fromisoformat(start_utc_str).replace(tzinfo=timezone.utc)
    dur = timedelta(minutes=5)
    return [t0+dur, t0+2*dur, t0+3*dur]
