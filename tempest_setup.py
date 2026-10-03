#!/usr/bin/env python3
"""Interactive setup; the token is never accepted as a command-line argument."""
import argparse
import getpass
import os
from pathlib import Path
import sys
import warnings

from tempest_weather import DEFAULT_CONFIG, TempestError, discover_stations, save_config


def setup(path=DEFAULT_CONFIG):
    token = os.environ.get('LYDIA_TEMPEST_TOKEN')
    if not token:
        if not sys.stdin.isatty():
            raise TempestError('Run setup in an interactive terminal for hidden token entry.')
        # getpass normally falls back to echoing stdin. Refuse that fallback.
        with warnings.catch_warnings():
            warnings.simplefilter('error', getpass.GetPassWarning)
            token = getpass.getpass('Tempest Personal Access Token (hidden): ').strip()
    stations = discover_stations(token)
    if len(stations) == 1:
        station = stations[0]
    else:
        print('Choose the station Lydia should use:')
        for number, station in enumerate(stations, 1):
            print(f"{number}. {station['name']} (station {station['station_id']})")
        while True:
            choice = input(f'Station [1–{len(stations)}]: ').strip()
            if choice.isdigit() and 1 <= int(choice) <= len(stations):
                station = stations[int(choice) - 1]
                break
            print('Enter one of the listed numbers.')
    save_config(token, station, path)
    print('Tempest setup saved privately. Lydia will discover the saved configuration on its next weather request.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path(os.environ.get('LYDIA_TEMPEST_CONFIG', DEFAULT_CONFIG)))
    args = parser.parse_args()
    try:
        setup(args.config)
        return 0
    except (TempestError, OSError, ValueError, getpass.GetPassWarning, EOFError, KeyboardInterrupt):
        # Do not print exception objects: network exceptions may contain token URLs.
        print('Tempest setup was not completed. Check the token/account, connection, and private configuration directory.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
