# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Common code for Cisco phones running the *enterprise* SIP firmware.

Enterprise firmware (sip78xx.*, sip88xx.* loads) is the firmware shipped for
use with Cisco Unified Communications Manager. Unlike the multiplatform (MPP /
3PCC) firmware handled by the wazo-cisco-sip plugin, it is provisioned over
TFTP with a CUCM style SEP<MAC>.cnf.xml file.
"""

from __future__ import annotations

import logging
import os
import re
from operator import itemgetter
from typing import TYPE_CHECKING
from xml.sax.saxutils import escape

try:
    from wazo_provd import plugins, synchronize, tzinform
    from wazo_provd.devices.config import RawConfigError
    from wazo_provd.devices.ident import DHCPRequest, RequestType
    from wazo_provd.devices.pgasso import BasePgAssociator, DeviceSupport
    from wazo_provd.plugins import (
        FetchfwPluginHelper,
        StandardPlugin,
        TemplatePluginHelper,
    )
    from wazo_provd.servers.http import HTTPNoListingFileService
    from wazo_provd.servers.http_site import Request
    from wazo_provd.servers.tftp.packet import Packet
    from wazo_provd.servers.tftp.service import TFTPFileService, TFTPRequest
    from wazo_provd.util import format_mac, norm_mac
except ImportError:
    # Compatibility with wazo < 24.02
    from provd import plugins, synchronize, tzinform
    from provd.devices.config import RawConfigError
    from provd.devices.ident import DHCPRequest, RequestType
    from provd.devices.pgasso import BasePgAssociator, DeviceSupport
    from provd.plugins import FetchfwPluginHelper, StandardPlugin, TemplatePluginHelper
    from provd.servers.http import HTTPNoListingFileService
    from provd.servers.http_site import Request
    from provd.servers.tftp.packet import Packet
    from provd.servers.tftp.service import TFTPFileService, TFTPRequest
    from provd.util import format_mac, norm_mac

from twisted.internet import defer

if TYPE_CHECKING:
    from typing import Any, Literal, TypedDict

    class DevInfoDict(TypedDict, total=False):
        vendor: Literal['Cisco']
        model: str
        mac: str


logger = logging.getLogger('plugin.wazo-cisco-sip-enterprise')

# featureID values of the <line> elements of a CUCM style configuration
FEATURE_ID_LINE = 9
FEATURE_ID_SPEED_DIAL = 2
FEATURE_ID_BLF_SPEED_DIAL = 21

# values of the <transportLayerProtocol> element
TRANSPORT_TCP = 1
TRANSPORT_UDP = 2


class BaseCiscoPgAssociator(BasePgAssociator):
    def __init__(self, models) -> None:
        super().__init__()
        self._models = models

    def _do_associate(
        self, vendor: str, model: str | None, version: str | None
    ) -> DeviceSupport | int:
        if vendor == 'Cisco':
            if version and 'MPP' in version:
                # multiplatform firmware, handled by the wazo-cisco-sip plugin
                return DeviceSupport.NONE
            if model in self._models:
                # Enterprise phones never advertise their firmware version
                # during provisioning, while multiplatform phones always do.
                # Score slightly higher than the wazo-cisco-sip plugin.
                return DeviceSupport.COMPLETE.value + 10
            return DeviceSupport.IMPROBABLE
        return DeviceSupport.IMPROBABLE


class BaseCiscoDHCPDeviceInfoExtractor:
    _VDI_REGEX = re.compile(r'\bPhone CP-(\d{4})\b')

    def extract(
        self, request: DHCPRequest, request_type: RequestType
    ) -> defer.Deferred:
        return defer.succeed(self._do_extract(request))

    def _do_extract(self, request: DHCPRequest) -> DevInfoDict | None:
        options = request['options']
        if 60 in options:
            return self._extract_from_vdi(options[60])
        return None

    def _extract_from_vdi(self, vdi: str) -> DevInfoDict | None:
        # Vendor class identifier:
        #   "Cisco Systems, Inc. IP Phone CP-8851\x00" (Cisco 8851 12.7.1)
        if vdi.startswith('Cisco Systems'):
            m = self._VDI_REGEX.search(vdi)
            if m:
                return {'vendor': 'Cisco', 'model': m.group(1)}
        return None


class BaseCiscoHTTPDeviceInfoExtractor:
    _FILENAME_REGEX = re.compile(r'^/SEP([\dA-F]{12})\.cnf\.xml(?:\.sgn)?$')

    def extract(self, request: Request, request_type: RequestType) -> defer.Deferred:
        return defer.succeed(self._do_extract(request))

    def _do_extract(self, request: Request) -> DevInfoDict | None:
        return _extract_from_filename(
            self._FILENAME_REGEX, request.path.decode('ascii')
        )


class BaseCiscoTFTPDeviceInfoExtractor:
    _FILENAME_REGEX = re.compile(r'^SEP([\dA-F]{12})\.cnf\.xml(?:\.sgn)?$')

    def extract(self, request: TFTPRequest, request_type: RequestType):
        return defer.succeed(self._do_extract(request))

    def _do_extract(self, request: TFTPRequest) -> DevInfoDict | None:
        packet: Packet = request['packet']
        return _extract_from_filename(
            self._FILENAME_REGEX, packet['filename'].decode('ascii')
        )

    def __repr__(self) -> str:
        return object.__repr__(self) + "-SIP-Enterprise"


def _extract_from_filename(regex: re.Pattern, filename: str) -> DevInfoDict | None:
    m = regex.match(filename)
    if not m:
        return None
    dev_info: DevInfoDict = {'vendor': 'Cisco'}
    try:
        dev_info['mac'] = norm_mac(m.group(1))
    except ValueError as e:
        logger.warning('Could not normalize MAC address: %s', e)
    return dev_info


_ZONE_MAP = {
    'Etc/GMT+12': 'Dateline Standard Time',
    'Pacific/Samoa': 'Samoa Standard Time ',
    'US/Hawaii': 'Hawaiian Standard Time ',
    'US/Alaska': 'Alaskan Standard/Daylight Time',
    'US/Pacific': 'Pacific Standard/Daylight Time',
    'US/Mountain': 'Mountain Standard/Daylight Time',
    'Etc/GMT+7': 'US Mountain Standard Time',
    'US/Central': 'Central Standard/Daylight Time',
    'America/Mexico_City': 'Mexico Standard/Daylight Time',
    'US/Eastern': 'Eastern Standard/Daylight Time',
    'Etc/GMT+5': 'US Eastern Standard Time',
    'Canada/Atlantic': 'Atlantic Standard/Daylight Time',
    'Etc/GMT+4': 'SA Western Standard Time',
    'Canada/Newfoundland': 'Newfoundland Standard/Daylight Time',
    'America/Sao_Paulo': 'South America Standard/Daylight Time',
    'Etc/GMT+3': 'SA Eastern Standard Time',
    'Etc/GMT+2': 'Mid-Atlantic Standard/Daylight Time',
    'Atlantic/Azores': 'Azores Standard/Daylight Time',
    'Europe/London': 'GMT Standard/Daylight Time',
    'Etc/GMT': 'Greenwich Standard Time',
    'Egypt': 'Egypt Standard/Daylight Time',
    'Europe/Athens': 'E. Europe Standard/Daylight Time',
    'Europe/Berlin': 'W. Europe Standard/Daylight Time',
    'Africa/Johannesburg': 'South Africa Standard Time ',
    'Asia/Jerusalem': 'Jerusalem Standard/Daylight Time',
    'Asia/Riyadh': 'Saudi Arabia Standard Time',
    'Europe/Moscow': 'Russian Standard/Daylight Time',
    'Iran': 'Iran Standard/Daylight Time',
    'Etc/GMT-4': 'Arabian Standard Time',
    'Asia/Kabul': 'Afghanistan Standard Time ',
    'Etc/GMT-5': 'West Asia Standard Time',
    'Asia/Calcutta': 'India Standard Time',
    'Etc/GMT-6': 'Central Asia Standard Time ',
    'Etc/GMT-7': 'SE Asia Standard Time',
    'Asia/Taipei': 'Taipei Standard Time',
    'Asia/Tokyo': 'Tokyo Standard Time',
    'Australia/ACT': 'Cen. Australia Standard/Daylight Time',
    'Australia/Brisbane': 'AUS Central Standard Time',
    'Etc/GMT-10': 'West Pacific Standard Time',
    'Australia/Tasmania': 'Tasmania Standard/Daylight Time',
    'Etc/GMT-11': 'Central Pacific Standard Time',
    'Etc/GMT-12': 'Fiji Standard Time',
}


def _gen_tz_map() -> dict[int, dict[str | None, str]]:
    result: dict[int, dict[str | None, str]] = {}
    for tz_name, param_value in _ZONE_MAP.items():
        tzinfo = tzinform.get_timezone_info(tz_name)
        inner_dict = result.setdefault(tzinfo['utcoffset'].as_minutes, {})
        if not tzinfo['dst']:
            inner_dict[None] = param_value
        else:
            inner_dict[tzinfo['dst']['as_string']] = param_value
    return result


class BaseCiscoSipEnterprisePlugin(StandardPlugin):
    _ENCODING = 'UTF-8'
    _TZ_MAP = _gen_tz_map()
    _TZ_VALUE_DEF = 'Eastern Standard/Daylight Time'
    _LOCALE = {
        # <locale>: (<name>, <lang code>, <network locale>)
        'de_DE': ('German_Germany', 'de_DE', 'Germany'),
        'en_US': ('English_United_States', 'en_US', 'United_States'),
        'es_ES': ('Spanish_Spain', 'es_ES', 'Spain'),
        'fr_FR': ('French_France', 'fr_FR', 'France'),
        'fr_CA': ('French_France', 'fr_FR', 'Canada'),
    }
    _NB_BUTTONS = {
        # <model>: number of programmable buttons without expansion module
        '7811': 0,
        '7821': 2,
        '7841': 4,
        '7861': 16,
        '8811': 5,
        '8841': 5,
        '8845': 5,
        '8851': 5,
        '8861': 5,
        '8865': 5,
    }
    _DTMF_OUT_OF_BAND = {
        'RTP-out-of-band': 'avt',
        'RTP-in-band': 'none',
        'SIP-INFO': 'avt_always',
    }
    _SENSITIVE_FILENAME_REGEX = re.compile(r'^SEP[0-9A-F]{12}\.cnf\.xml$')

    def __init__(self, app, plugin_dir, gen_cfg, spec_cfg):
        super().__init__(app, plugin_dir, gen_cfg, spec_cfg)

        self._tpl_helper = TemplatePluginHelper(plugin_dir)

        downloaders = FetchfwPluginHelper.new_downloaders(gen_cfg.get('proxies'))
        fetchfw_helper = FetchfwPluginHelper(plugin_dir, downloaders)

        self.services = fetchfw_helper.services()

        self.http_service = HTTPNoListingFileService(self._tftpboot_dir)
        self.tftp_service = TFTPFileService(self._tftpboot_dir)

    dhcp_dev_info_extractor = BaseCiscoDHCPDeviceInfoExtractor()
    http_dev_info_extractor = BaseCiscoHTTPDeviceInfoExtractor()
    tftp_dev_info_extractor = BaseCiscoTFTPDeviceInfoExtractor()

    def _add_locale(self, raw_config):
        locale = raw_config.get('locale')
        if locale in self._LOCALE:
            raw_config['XX_locale'] = self._LOCALE[locale]

    def _tzinfo_to_value(self, tzinfo):
        utcoffset_m = tzinfo['utcoffset'].as_minutes
        if utcoffset_m not in self._TZ_MAP:
            # No UTC offset matching. Let's try finding one relatively close...
            for supp_offset in [30, -30, 60, -60]:
                if utcoffset_m + supp_offset in self._TZ_MAP:
                    utcoffset_m += supp_offset
                    break
            else:
                return self._TZ_VALUE_DEF

        dst_map = self._TZ_MAP[utcoffset_m]
        if tzinfo['dst']:
            dst_key = tzinfo['dst']['as_string']
        else:
            dst_key = None
        if dst_key not in dst_map:
            # No DST rules matching. Fallback on all-standard time or random
            # DST rule in last resort...
            if None in dst_map:
                dst_key = None
            else:
                dst_key = list(dst_map)[0]
        return dst_map[dst_key]

    def _add_timezone(self, raw_config):
        raw_config['XX_timezone'] = self._TZ_VALUE_DEF
        if 'timezone' in raw_config:
            try:
                tzinfo = tzinform.get_timezone_info(raw_config['timezone'])
            except tzinform.TimezoneNotFoundError as e:
                logger.info('Unknown timezone: %s', e)
            else:
                raw_config['XX_timezone'] = self._tzinfo_to_value(tzinfo)

    def _add_xivo_phonebook_url(self, raw_config):
        plugins.add_xivo_phonebook_url(raw_config, 'cisco', entry_point='menu')

    def _add_call_managers(self, raw_config):
        # The lines use the USECALLMANAGER proxy, i.e. they register to the
        # members of the call manager group, in priority order. There is only
        # one call manager group per device, so it is built from the first
        # line, which is where Wazo sets the proxies.
        first_line = raw_config['sip_lines'][min(raw_config['sip_lines'], key=int)]
        call_managers = [
            {
                'ip': first_line.get('proxy_ip') or raw_config['sip_proxy_ip'],
                'port': first_line.get('proxy_port')
                or raw_config.get('sip_proxy_port', '5060'),
            }
        ]
        backup_proxy_ip = first_line.get('backup_proxy_ip') or raw_config.get(
            'sip_backup_proxy_ip'
        )
        if backup_proxy_ip:
            call_managers.append(
                {
                    'ip': backup_proxy_ip,
                    'port': first_line.get('backup_proxy_port')
                    or raw_config.get('sip_backup_proxy_port', '5060'),
                }
            )
        raw_config['XX_call_managers'] = call_managers

    def _add_transport(self, raw_config):
        transport = raw_config.get('sip_transport', 'udp')
        if transport == 'tcp':
            raw_config['XX_transport'] = TRANSPORT_TCP
        else:
            if transport != 'udp':
                logger.info('Unsupported SIP transport %s, using UDP', transport)
            raw_config['XX_transport'] = TRANSPORT_UDP

    def _add_dtmf(self, raw_config):
        dtmf_mode = raw_config.get('sip_dtmf_mode')
        raw_config['XX_dtmf_out_of_band'] = self._DTMF_OUT_OF_BAND.get(dtmf_mode, 'avt')

    def _add_buttons(self, raw_config, model):
        """Build the list of <line> buttons: SIP lines first, then funckeys.

        Funckeys keep their position as button number. A funckey whose position
        is already taken by a SIP line is ignored.
        """
        buttons: dict[int, dict[str, Any]] = {}
        for line_no, line in sorted(
            raw_config['sip_lines'].items(), key=lambda item: int(item[0])
        ):
            buttons[int(line_no)] = {
                'feature_id': FEATURE_ID_LINE,
                'line_index': int(line_no),
                'line': line,
                'label': escape(line.get('number') or line['username']),
            }

        nb_buttons = self._NB_BUTTONS.get(model)
        for funckey_no, funckey in sorted(
            raw_config['funckeys'].items(), key=itemgetter(0)
        ):
            button_no = int(funckey_no)
            if button_no in buttons:
                logger.info('Funckey %s is hidden by a SIP line', funckey_no)
                continue
            if nb_buttons is not None and button_no > nb_buttons:
                logger.info(
                    'Model %s has less than %s programmable buttons', model, button_no
                )
                continue
            funckey_type = funckey['type']
            if funckey_type == 'speeddial':
                feature_id = FEATURE_ID_SPEED_DIAL
            elif funckey_type == 'blf':
                feature_id = FEATURE_ID_BLF_SPEED_DIAL
            else:
                logger.info('Unsupported funckey type: %s', funckey_type)
                continue
            value = funckey['value']
            buttons[button_no] = {
                'feature_id': feature_id,
                'number': escape(value),
                'label': escape(funckey.get('label') or value),
            }
        raw_config['XX_buttons'] = sorted(buttons.items())

    def _dev_specific_filename(self, device: dict[str, str]) -> str:
        # Return the device specific filename (not pathname) of device
        formatted_mac = format_mac(device['mac'], separator='', uppercase=True)
        return f'SEP{formatted_mac}.cnf.xml'

    def _check_config(self, raw_config):
        if 'tftp_port' not in raw_config:
            raise RawConfigError('only support configuration via TFTP')

    def _check_device(self, device):
        if 'mac' not in device:
            raise Exception('MAC address needed for device configuration')

    def configure(self, device, raw_config):
        self._check_config(raw_config)
        self._check_device(device)
        filename = self._dev_specific_filename(device)
        tpl = self._tpl_helper.get_dev_template(filename, device)

        self._add_locale(raw_config)
        self._add_timezone(raw_config)
        self._add_xivo_phonebook_url(raw_config)
        self._add_call_managers(raw_config)
        self._add_transport(raw_config)
        self._add_dtmf(raw_config)
        self._add_buttons(raw_config, device.get('model'))

        path = os.path.join(self._tftpboot_dir, filename)
        self._tpl_helper.dump(tpl, raw_config, path, self._ENCODING, errors='replace')

    def deconfigure(self, device):
        path = os.path.join(self._tftpboot_dir, self._dev_specific_filename(device))
        try:
            os.remove(path)
        except OSError as e:
            # ignore
            logger.info('error while removing file: %s', e)

    def synchronize(self, device, raw_config):
        return synchronize.standard_sip_synchronize(device)

    def get_remote_state_trigger_filename(self, device):
        if 'mac' not in device:
            return None

        return self._dev_specific_filename(device)

    def is_sensitive_filename(self, filename):
        return bool(self._SENSITIVE_FILENAME_REGEX.match(filename))
