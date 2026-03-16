import datetime

# Момент запуску процесу (UTC)
START_TIME: datetime.datetime = datetime.datetime.now(datetime.timezone.utc)

state = {
    "last_cycle_time": None,   # datetime UTC — коли закінчився останній цикл
    "last_items_count": 0,     # скільки лотів повернув eBay в останньому циклі
    "total_sent": 0,           # скільки match-сповіщень надіслано за весь час роботи
}
