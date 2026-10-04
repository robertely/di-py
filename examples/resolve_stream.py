import os
import sys

from difm import Client


station_key = sys.argv[1] if len(sys.argv) > 1 else "trance"

with Client(listen_key=os.environ["DIFM_LISTEN_KEY"]) as di:
    print(di.stream_url(station_key))
