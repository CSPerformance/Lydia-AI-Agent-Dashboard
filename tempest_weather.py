"""Private Tempest REST provider. Never return credentials or raw provider documents.

API: https://weatherflow.github.io/Tempest/api/swagger/swagger.json
Station observation values are SI regardless of station_units preferences.
"""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import tempfile
import threading
import time
from datetime import datetime, timezone
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_CONFIG = Path(os.environ.get('LYDIA_TEMPEST_CONFIG', './state/tempest/config.json')).expanduser()
API_ROOT = 'https://swd.weatherflow.com/swd/rest'
CACHE_SECONDS = 60
FRESH_SECONDS = 600
MAX_STALE_SECONDS = 7200


class TempestError(ValueError):
    """Only fixed, safe messages may cross this boundary."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TempestError('Tempest redirected the request; no credentials were forwarded.')


def api_read(token, endpoint):
    if not re.fullmatch(r'/stations|/observations/station/[1-9][0-9]*', endpoint):
        raise TempestError('Invalid Tempest endpoint.')
    if not isinstance(token, str) or not token.strip() or len(token) > 4096:
        raise TempestError('A valid Tempest token is required.')
    # Official PAT authentication uses a query parameter. This URL stays server-side,
    # out of shared weather caches, exceptions, application logs and web responses.
    url = API_ROOT + endpoint + '?' + urllib.parse.urlencode({'token': token})
    request = urllib.request.Request(url, headers={'Accept': 'application/json',
                                                  'User-Agent': 'Lydia-Tempest/1.0'})
    failure = None
    try:
        # Do not forward tokens to environment-configured HTTP proxies or redirects.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
        with opener.open(request, timeout=8) as response:
            if response.status != 200 or response.headers.get_content_type() != 'application/json':
                raise ValueError('response')
            body = response.read(2 * 1024 * 1024 + 1)
        if len(body) > 2 * 1024 * 1024:
            raise ValueError('size')
        data = json.loads(body)
        if not isinstance(data, dict) or (data.get('status') or {}).get('status_code') != 0:
            raise ValueError('status')
        return data
    except urllib.error.HTTPError as exc:
        failure = ('Tempest authentication failed; run the setup utility to replace the token.'
                   if exc.code in (401, 403) else
                   'Tempest rate limit reached; retry later.' if exc.code == 429 else
                   'Tempest is unavailable; retry later.')
    except (OSError, ValueError, TypeError, AttributeError, urllib.error.URLError):
        failure = 'Tempest is unavailable or returned an invalid response.'
    # Raise outside the handler so even exception chaining cannot retain a token URL.
    raise TempestError(failure)


def _number(value):
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def _text(value, fallback=''):
    return re.sub(r'[\x00-\x1f\x7f-\x9f]', '', str(value or fallback))[:100]


def station_metadata(row):
    if not isinstance(row, dict) or not isinstance(row.get('station_id'), int) or isinstance(row['station_id'], bool) or row['station_id'] <= 0:
        raise TempestError('Invalid Tempest station metadata.')
    lat, lon = _number(row.get('latitude')), _number(row.get('longitude'))
    if lat is None or lon is None or not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise TempestError('Tempest station coordinates are unavailable.')
    zone = row.get('timezone', 'UTC')
    try:
        ZoneInfo(zone)
    except (ValueError, TypeError, ZoneInfoNotFoundError):
        zone = 'UTC'
    devices = []
    device_rows = row.get('devices') or []
    meta = row.get('station_meta') or {}
    if not isinstance(device_rows, list) or not isinstance(meta, dict):
        raise TempestError('Invalid Tempest station metadata.')
    for device in device_rows:
        if isinstance(device, dict) and type(device.get('device_id')) is int:
            devices.append({'device_id': device['device_id'], 'device_type': _text(device.get('device_type'))})
    return {'station_id': row['station_id'], 'name': _text(row.get('name'), 'Tempest station'),
            'latitude': lat, 'longitude': lon, 'timezone': zone,
            'elevation_m': _number(meta.get('elevation', row.get('elevation_m'))),
            'devices': devices}


def discover_stations(token):
    data = api_read(token, '/stations')
    rows = data.get('stations', data.get('locations', []))
    if not isinstance(rows, list):
        raise TempestError('Tempest station discovery failed.')
    stations = [station_metadata(row) for row in rows]
    if not stations:
        raise TempestError('No stations were found for this token. Check its account in Tempest.')
    return stations


def save_config(token, station, path=DEFAULT_CONFIG):
    """Atomic owner-only secret file, outside the repository by default."""
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.parent.is_symlink() or path.parent.stat().st_mode & 0o077:
        raise TempestError('Tempest configuration directory must be private (mode 0700).')
    document = {'version': 1, 'token': token, 'station': station_metadata(station)}
    fd, temporary = tempfile.mkstemp(prefix='.tempest-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(document, handle)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def read_config(path=DEFAULT_CONFIG):
    path = Path(path)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    except OSError:
        raise TempestError('Tempest configuration cannot be read safely.') from None
    try:
        with os.fdopen(fd, 'r', encoding='utf-8') as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.geteuid():
                raise TempestError('Tempest configuration must be owner-only (mode 0600).')
            data = json.loads(handle.read(65537))
        if not isinstance(data, dict) or not isinstance(data.get('token'), str) or not data['token'].strip():
            raise ValueError('configuration')
        return {'token': data['token'], 'station': station_metadata(data['station'])}
    except (OSError, ValueError, KeyError, TypeError):
        raise TempestError('Tempest configuration is invalid or not private; run setup again.') from None


def normalize_observation(data, station, now):
    if data.get('station_id') != station['station_id']:
        raise TempestError('Tempest returned a different station.')
    rows = data.get('obs')
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
        raise TempestError('Tempest has no station observation available.')
    row = rows[0]
    timestamp = _number(row.get('timestamp'))
    if timestamp is None or timestamp <= 0 or timestamp > now + 120:
        raise TempestError('Tempest observation timestamp is invalid.')
    temp = _number(row.get('air_temperature'))
    if temp is None:
        raise TempestError('Tempest outdoor temperature is unavailable.')
    def value(key, factor=1, offset=0, digits=1):
        number = _number(row.get(key))
        return round(number * factor + offset, digits) if number is not None else None
    observation = {
        'station': station['name'], 'station_id': station['station_id'],
        'timestamp': datetime.fromtimestamp(timestamp, timezone.utc).isoformat(),
        'temperature': value('air_temperature', 1.8, 32), 'temperatureUnit': 'F',
        'feels_like_f': value('feels_like', 1.8, 32), 'dew_point_f': value('dew_point', 1.8, 32),
        'heat_index_f': value('heat_index', 1.8, 32), 'wind_chill_f': value('wind_chill', 1.8, 32),
        'wet_bulb_f': value('wet_bulb_temperature', 1.8, 32),
        'wet_bulb_globe_f': value('wet_bulb_globe_temperature', 1.8, 32),
        'delta_t_f': value('delta_t', 1.8),
        'air_density_lbft3': value('air_density', 0.06242796, digits=4),
        'humidity_pct': value('relative_humidity'),
        'station_pressure_inhg': value('barometric_pressure', 0.029529983, digits=2),
        'sea_level_pressure_inhg': value('sea_level_pressure', 0.029529983, digits=2),
        'pressure_trend': row.get('pressure_trend') if row.get('pressure_trend') in ('rising', 'falling', 'steady', 'unknown') else None,
        'wind_mph': value('wind_avg', 2.236936292), 'wind_gust_mph': value('wind_gust', 2.236936292),
        'wind_lull_mph': value('wind_lull', 2.236936292), 'wind_degrees': value('wind_direction'),
        'precip_today_in': value('precip_accum_local_day', 1 / 25.4, digits=3),
        'precip_today_adjusted_in': value('precip_accum_local_day_final', 1 / 25.4, digits=3),
        'precip_yesterday_in': value('precip_accum_local_yesterday', 1 / 25.4, digits=3),
        'precip_yesterday_adjusted_in': value('precip_accum_local_yesterday_final', 1 / 25.4, digits=3),
        'precip_minutes_today': value('precip_minutes_local_day', digits=0),
        'precip_minutes_yesterday': value('precip_minutes_local_yesterday', digits=0),
        'precip_minutes_yesterday_adjusted': value('precip_minutes_local_yesterday_final', digits=0),
        'precip_analysis_yesterday': {0: 'No adjustment', 1: 'Nearcast adjustment enabled',
                                     2: 'Nearcast adjustment hidden by station preference'}.get(_number(row.get('precip_analysis_type_yesterday'))),
        'precip_interval_in': value('precip', 1 / 25.4, digits=3),
        'precip_last_hour_in': value('precip_accum_last_1hr', 1 / 25.4, digits=3),
        'precip_type': {0: 'None', 1: 'Rain', 2: 'Hail', 3: 'Rain and hail'}.get(_number(row.get('precip_type'))),
        'uv_index': value('uv'), 'solar_radiation_wm2': value('solar_radiation'),
        'illuminance_lux': value('brightness'),
        'lightning_count_interval': value('lightning_strike_count', digits=0),
        'lightning_count_1hr': value('lightning_strike_count_last_1hr', digits=0),
        'lightning_count_3hr': value('lightning_strike_count_last_3hr', digits=0),
        'lightning_last_distance_mi': value('lightning_strike_last_distance', 0.621371192),
        'condition': 'Personal station observation',
    }
    if _number(row.get('station_pressure')) is not None:
        observation['station_pressure_inhg'] = value('station_pressure', 0.029529983, digits=2)
    last_strike = _number(row.get('lightning_strike_last_epoch'))
    observation['lightning_last_time'] = (datetime.fromtimestamp(last_strike, timezone.utc).isoformat()
                                          if last_strike is not None and 0 < last_strike <= now else None)
    direction = _number(row.get('wind_direction'))
    observation['wind_cardinal'] = ('N NNE NE ENE E ESE SE SSE S SSW SW WSW W WNW NW NNW'.split()[int((direction % 360 + 11.25) / 22.5) % 16]
                                    if direction is not None and 0 <= direction <= 360 else None)
    # Never carry yesterday's accumulated rain into today's display from a stale sample.
    zone = ZoneInfo(station['timezone'])
    if datetime.fromtimestamp(timestamp, zone).date() != datetime.fromtimestamp(now, zone).date():
        _clear_calendar_readings(observation)
    return observation


def _clear_calendar_readings(observation):
    # Both 'today' and 'yesterday' are relative to the observation's local date.
    for key in ('precip_today_in', 'precip_today_adjusted_in', 'precip_yesterday_in',
                'precip_yesterday_adjusted_in', 'precip_minutes_today', 'precip_minutes_yesterday',
                'precip_minutes_yesterday_adjusted', 'precip_analysis_yesterday'):
        observation[key] = None


class TempestProvider:
    def __init__(self, path=DEFAULT_CONFIG):
        self.path = Path(path)
        self._lock = threading.RLock()
        self._identity = None
        self._station = None
        self._cached = None
        self._last_attempt = 0
        self._failed = False

    def _configuration(self):
        config = read_config(self.path)
        token = os.environ.get('LYDIA_TEMPEST_TOKEN') or (config or {}).get('token')
        if not token:
            return None
        fingerprint = hashlib.sha256(token.encode()).hexdigest()
        # An environment override must rediscover its own stations, not reuse a previous account.
        station = (config or {}).get('station') if token == (config or {}).get('token') else None
        identity = (fingerprint, json.dumps(station, sort_keys=True))
        if identity != self._identity:
            self._identity, self._station, self._cached = identity, station, None
            self._last_attempt, self._failed = 0, False
        if self._station is None:
            stations = discover_stations(token)
            if len(stations) != 1:
                raise TempestError('Multiple Tempest stations found. Run python3 tempest_setup.py to choose one.')
            self._station = stations[0]
        return token, self._station

    def location(self):
        with self._lock:
            config = self._configuration()
            if not config:
                return None
            station = config[1]
            return {'location_enabled': True, 'latitude': station['latitude'], 'longitude': station['longitude'],
                    'label': station['name'], 'precision_source': 'tempest',
                    'revision': 'tempest-' + str(station['station_id'])}

    def current(self, force=False):
        with self._lock:
            config = self._configuration()
            if not config:
                return None
            token, station = config
            now = time.time()
            # At most one upstream request per minute, including refresh and outage retries.
            if now - self._last_attempt >= CACHE_SECONDS:
                self._last_attempt = now
                try:
                    data = api_read(token, '/observations/station/' + str(station['station_id']))
                    observation = normalize_observation(data, station, now)
                    self._cached = {'observation': observation, 'retrieved_at': now}
                    self._failed = False
                except TempestError:
                    self._failed = True
                    if not self._cached:
                        raise
            if not self._cached:
                raise TempestError('Tempest is unavailable; retry in one minute.')
            result = copy.deepcopy(self._cached)
            stamp = datetime.fromisoformat(result['observation']['timestamp']).timestamp()
            age = max(0, now - stamp)
            if age > MAX_STALE_SECONDS:
                raise TempestError('Tempest station is offline; its last observation is over two hours old.')
            # Re-normalize the day boundary even when using a cached observation.
            zone = ZoneInfo(station['timezone'])
            if datetime.fromtimestamp(now, zone).date() != datetime.fromtimestamp(stamp, zone).date():
                _clear_calendar_readings(result['observation'])
            result.update(provider='WeatherFlow Tempest', verified=True,
                          observation_kind='Tempest personal station observation', time_zone=station['timezone'],
                          source_updated=result['observation']['timestamp'], source_age_seconds=age,
                          stale=self._failed or age > FRESH_SECONDS, cached=now > result['retrieved_at'],
                          refresh_failed=self._failed, freshness='known')
            return result
