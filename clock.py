import board
import busio
import displayio
import terminalio  # Just a font
import adafruit_ili9341
from adafruit_display_text import label
import adafruit_requests
import gc
import time
import ssl
import json
import wifi
import socketpool
import supervisor
from secrets import secrets
from adafruit_datetime import datetime

TIME_ZONE = -7  # "Americas/Denver"
REQUEST_URL = "http://worldtimeapi.org/api/timezone/America/Denver"
RESYNC_HOUR = 3

# variable assignments
unix_time = 0
last_resync = {"day": 0, "month": 0, "year": 0}
start_time = time.monotonic()


def readable_time(time):
    dt = datetime.fromtimestamp(time)
    hour = dt.hour + TIME_ZONE  # adjust timezone here

    if hour < 0:
        hour = hour + 24

    am_pm = "AM"
    if hour / 12 >= 1:
        am_pm = "PM"

    if hour - 12 >= 0:
        hour = hour - 12

    if hour == 0:
        hour = 12

    return "{:d}:{:02d}:{:02d} {}".format(hour, dt.minute, dt.second, am_pm)


def get_real_time():
    # Connect to Wi-Fi
    print("\n===============================")
    print("Connecting to WiFi...")
    pool = socketpool.SocketPool(wifi.radio)
    requests = adafruit_requests.Session(pool, ssl.create_default_context())
    while not wifi.radio.ipv4_address:
        try:
            wifi.radio.connect(secrets["ssid"], secrets["password"])
        except ConnectionError as e:
            print("Connection Error:", e)
            print("Retrying in 10 seconds")
        time.sleep(3)
        gc.collect()
    print("Connected!\n")

    res = requests.get(url=REQUEST_URL).json()
    return res["unixtime"]

# Tries to resync once a day
def scheduleResync(unixtime):
    global last_resync
    global start_time
    dt = datetime.fromtimestamp(unixtime + int(TIME_ZONE * 3.6e3))

    if dt.hour != RESYNC_HOUR:
        return
    if (
        dt.day == last_resync["day"]
        and dt.month == last_resync["month"]
        and dt.year == last_resync["year"]
    ):
        return

    print("Resyncing...")
    unix_time = get_real_time()
    last_resync = {"day": dt.day, "month": dt.month, "year": dt.year}
    start_time = time.monotonic()


cs = board.IO4
rst = board.IO5
dc = board.IO6
MOSI = board.IO7
SCK = board.IO15
LED = board.IO16
MISO = board.IO17

displayio.release_displays()

# spi = busio.SPI(clock=board.GP2, MOSI=board.GP3, MISO=board.GP4)
spi = busio.SPI(clock=SCK, MOSI=MOSI, MISO=MISO)

unix_time = get_real_time()
rt = readable_time(unix_time)

display_bus = displayio.FourWire(spi, command=dc, chip_select=cs)
display = adafruit_ili9341.ILI9341(display_bus, width=320, height=240)

# Make the display context
splash = displayio.Group()
display.show(splash)

# Draw a green background
color_bitmap = displayio.Bitmap(display.width, display.height, 1)
color_palette = displayio.Palette(1)
color_palette[0] = 0x00FF00  # Bright Green

bg_sprite = displayio.TileGrid(color_bitmap, pixel_shader=color_palette, x=0, y=0)

splash.append(bg_sprite)

# Draw a smaller inner rectangle
inner_bitmap = displayio.Bitmap(display.width - 40, display.height - 40, 1)
inner_palette = displayio.Palette(1)
inner_palette[0] = 0xAA0088  # Purple
inner_sprite = displayio.TileGrid(inner_bitmap, pixel_shader=inner_palette, x=20, y=20)
splash.append(inner_sprite)

# Options
group_scale = 3
text_scale = 1
# Draw a label
text_group = displayio.Group(scale=group_scale, x=0, y=0)
updating_label = label.Label(font=terminalio.FONT, text=rt, scale=text_scale)
updating_label.anchor_point = (0.5, 0.5)
updating_label.anchored_position = (
    display.width / 2 / group_scale,
    display.height / 2 / group_scale,
)
text_group.append(updating_label)  # Subgroup for text scaling
splash.append(text_group)

while True:
    curr_time = time.monotonic()
    elapsed_time = int(curr_time - start_time)
    scheduleResync(unix_time + elapsed_time)
    rt = readable_time(unix_time + elapsed_time)
    updating_label.text = rt
    time.sleep(1)
