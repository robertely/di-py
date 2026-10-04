import os

from difm import Client


listen_key = os.environ["DIFM_LISTEN_KEY"]

with Client(listen_key=listen_key) as di:
    for station in di.my_stations():
        print(f"{station.name:32} {station.key}")
        print(f"  playlist: {di.stream_url(station, resolve=False)}")
