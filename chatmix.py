import subprocess
import re

# The name of the headset, as it appears in lsusb.
# Not supported changing this to other headsets.
HEADSET_NAME = "SteelSeries ApS Arctis Nova 7"
HEADSET_ALSA_NAME = "alsa_output.usb-SteelSeries_Arctis_Nova_7-00.analog-stereo"  # pactl list short sinks
CHATMIX_SINK = "chatmix"
GAMEMIX_SINK = "gamemix"


def execute_subprocess(command: str):
    """
    Takes a command string and executes it in a shell and returns the result.
    """
    return subprocess.check_output(command.split(" "))


def list_sinks(filter: str):
    """
    Lists all the sinks that match the filter.
    """
    return (
        execute_subprocess(f"pactl list short sinks | grep {filter}")
        .decode("utf-8")
        .split(" ")
    )


def create_audio_sink_if_not_exists(sink_name: str):
    """
    Creates a new audio sink if it doesn't exist.
    """
    if sink_name not in execute_subprocess("pactl list short sinks").decode("utf-8"):
        execute_subprocess(
            f"pactl load-module module-null-sink media.class=Audio/Sink sink_name={sink_name} channel_map=front-left,front-right"
        )


def link_sink_to_sink(sink_name: str, sink_to_link: str):
    """
    Set monitors of sink_name to playbacks of sink_to_link.
    """
    if sink_name not in execute_subprocess("pactl list short sinks").decode("utf-8"):
        return

    if sink_to_link not in execute_subprocess("pactl list short sinks").decode("utf-8"):
        return

    execute_subprocess(
        f"pactl load-module module-loopback source={sink_name}.monitor sink={sink_to_link}"
    )


def set_volume(sink_name: str, volume: int):
    """
    Sets the volume of a sink to a specific value.
    """
    if sink_name not in execute_subprocess("pactl list short sinks").decode("utf-8"):
        return

    execute_subprocess(f"pactl set-sink-volume {sink_name} {volume}%")


def get_device_info(device_name: str):
    """
    Uses Regex to search the output of lsusb for the bus and device number of a device.
    """

    # Get the device bus/deviceid/vendorid/productid
    output = execute_subprocess("lsusb").decode("utf-8").split("\n")
    regex = re.compile(r"Bus (\d{3}) Device (\d{3}): ID (\w{4}):(\w{4}) " + device_name)
    matches = list(filter(regex.search, output))

    if len(matches) == 0:
        return None

    return (
        tuple(map(int, regex.search(matches[0]).groups()[:2])),  # bus/deviceid
        regex.search(matches[0]).groups()[2:],  # vendorid/productid
    )


def get_mix_data_loop(bus: int, device: int, callback: object):
    """
    Uses the bus and device number to get the chatmix data from the device.
    Runs the callback function like: callback(game_volume: int, chat_volume: int)
    """
    process = subprocess.Popen(
        f"usbhid-dump -s {bus}:{device} -f -e stream -t 0",
        shell=True,
        stdout=subprocess.PIPE,
    )
    while process.poll() is None:
        output = process.stdout.readline()
        if b" 45 " in output:
            output = output.decode("utf-8").strip().replace(" ", "")[2:6]
            callback(int(output[:2], 16), int(output[2:], 16))


def main():
    busdevice, _ = get_device_info(HEADSET_NAME)

    create_audio_sink_if_not_exists(CHATMIX_SINK)
    create_audio_sink_if_not_exists(GAMEMIX_SINK)

    link_sink_to_sink(CHATMIX_SINK, HEADSET_ALSA_NAME)
    link_sink_to_sink(GAMEMIX_SINK, HEADSET_ALSA_NAME)

    def callback(game_volume: int, chat_volume: int):
        set_volume(GAMEMIX_SINK, game_volume)
        set_volume(CHATMIX_SINK, chat_volume)

    get_mix_data_loop(
        *busdevice, lambda game_volume, chat_volume: callback(game_volume, chat_volume)
    )


if __name__ == "__main__":
    main()
