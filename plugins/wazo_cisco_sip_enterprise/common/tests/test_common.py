# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock

import pytest
from jinja2 import Environment, FileSystemLoader

from ..common import (
    BaseCiscoDHCPDeviceInfoExtractor,
    BaseCiscoHTTPDeviceInfoExtractor,
    BaseCiscoPgAssociator,
    BaseCiscoSipEnterprisePlugin,
    BaseCiscoTFTPDeviceInfoExtractor,
    DeviceSupport,
)

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), '..', 'templates')


@pytest.fixture
def plugin():
    # skip StandardPlugin.__init__, the tested methods don't need it
    return BaseCiscoSipEnterprisePlugin.__new__(BaseCiscoSipEnterprisePlugin)


@pytest.fixture
def raw_config():
    return {
        'ip': '192.168.10.60',
        'tftp_port': 69,
        'http_port': 8667,
        'sip_proxy_ip': '192.168.10.60',
        'sip_dtmf_mode': 'RTP-out-of-band',
        'exten_voicemail': '*98',
        'ntp_enabled': True,
        'ntp_ip': '192.168.10.1',
        'locale': 'de_DE',
        'timezone': 'Europe/Berlin',
        'sip_lines': {
            '1': {
                'username': 'abcdef12',
                'auth_username': 'abcdef12',
                'password': 'secret&<>',
                'display_name': 'Niko & Co',
                'number': '1001',
            },
        },
        'funckeys': {
            '2': {'type': 'speeddial', 'value': '1002', 'label': 'Küche'},
            '3': {'type': 'blf', 'value': '1003'},
            '4': {'type': 'park', 'value': '700'},
        },
    }


class TestDeviceInfoExtractors:
    def test_dhcp_vdi(self):
        extractor = BaseCiscoDHCPDeviceInfoExtractor()
        vdi = 'Cisco Systems, Inc. IP Phone CP-8851\x00'
        assert extractor._extract_from_vdi(vdi) == {'vendor': 'Cisco', 'model': '8851'}

    def test_dhcp_vdi_not_cisco(self):
        extractor = BaseCiscoDHCPDeviceInfoExtractor()
        assert extractor._extract_from_vdi('yealink') is None

    @pytest.mark.parametrize(
        'filename', ['SEPCC98915400BA.cnf.xml', 'SEPCC98915400BA.cnf.xml.sgn']
    )
    def test_tftp(self, filename):
        extractor = BaseCiscoTFTPDeviceInfoExtractor()
        request = {'packet': {'filename': filename.encode('ascii')}}
        assert extractor._do_extract(request) == {
            'vendor': 'Cisco',
            'mac': 'cc:98:91:54:00:ba',
        }

    def test_tftp_other_file(self):
        extractor = BaseCiscoTFTPDeviceInfoExtractor()
        request = {'packet': {'filename': b'dialplan.xml'}}
        assert extractor._do_extract(request) is None

    def test_http(self):
        extractor = BaseCiscoHTTPDeviceInfoExtractor()
        request = MagicMock(path=b'/SEPCC98915400BA.cnf.xml')
        assert extractor._do_extract(request) == {
            'vendor': 'Cisco',
            'mac': 'cc:98:91:54:00:ba',
        }


class TestPgAssociator:
    def setup_method(self):
        self.associator = BaseCiscoPgAssociator(['8851'])

    def test_known_model(self):
        support = self.associator._do_associate('Cisco', '8851', None)
        assert support > DeviceSupport.COMPLETE

    def test_mpp_firmware(self):
        support = self.associator._do_associate('Cisco', '8851', '12.0.7MPP0201-66')
        assert support == DeviceSupport.NONE

    def test_unknown_model(self):
        support = self.associator._do_associate('Cisco', '7960', None)
        assert support == DeviceSupport.IMPROBABLE

    def test_other_vendor(self):
        support = self.associator._do_associate('Yealink', 'T46S', None)
        assert support == DeviceSupport.IMPROBABLE


class TestPlugin:
    def test_dev_specific_filename(self, plugin):
        device = {'mac': 'cc:98:91:54:00:ba'}
        assert plugin._dev_specific_filename(device) == 'SEPCC98915400BA.cnf.xml'

    def test_is_sensitive_filename(self, plugin):
        assert plugin.is_sensitive_filename('SEPCC98915400BA.cnf.xml')
        assert not plugin.is_sensitive_filename('dialplan.xml')

    def test_buttons(self, plugin, raw_config):
        plugin._add_buttons(raw_config, '8851')

        buttons = dict(raw_config['XX_buttons'])
        assert sorted(buttons) == [1, 2, 3]
        assert buttons[1]['feature_id'] == 9
        assert buttons[1]['label'] == '1001'
        assert buttons[2] == {'feature_id': 2, 'number': '1002', 'label': 'Küche'}
        assert buttons[3] == {'feature_id': 21, 'number': '1003', 'label': '1003'}

    def test_buttons_funckey_hidden_by_line(self, plugin, raw_config):
        raw_config['funckeys'] = {'1': {'type': 'speeddial', 'value': '1002'}}
        plugin._add_buttons(raw_config, '8851')

        assert [no for no, _ in raw_config['XX_buttons']] == [1]

    def test_buttons_more_than_model(self, plugin, raw_config):
        raw_config['funckeys'] = {'6': {'type': 'speeddial', 'value': '1002'}}
        plugin._add_buttons(raw_config, '8851')

        assert [no for no, _ in raw_config['XX_buttons']] == [1]

    def test_timezone(self, plugin, raw_config):
        plugin._add_timezone(raw_config)
        assert raw_config['XX_timezone'] == 'W. Europe Standard/Daylight Time'

    def test_transport(self, plugin, raw_config):
        plugin._add_transport(raw_config)
        assert raw_config['XX_transport'] == 2

        raw_config['sip_transport'] = 'tcp'
        plugin._add_transport(raw_config)
        assert raw_config['XX_transport'] == 1

    def test_call_manager_from_line(self, plugin, raw_config):
        del raw_config['sip_proxy_ip']
        raw_config['sip_lines']['1']['proxy_ip'] = '192.168.10.60'
        raw_config['sip_lines']['1']['backup_proxy_ip'] = '192.168.10.61'
        plugin._add_call_managers(raw_config)
        assert raw_config['XX_call_managers'] == [
            {'ip': '192.168.10.60', 'port': '5060'},
            {'ip': '192.168.10.61', 'port': '5060'},
        ]

    def test_backup_proxy(self, plugin, raw_config):
        raw_config['sip_backup_proxy_ip'] = '192.168.10.61'
        plugin._add_call_managers(raw_config)
        assert [cm['ip'] for cm in raw_config['XX_call_managers']] == [
            '192.168.10.60',
            '192.168.10.61',
        ]


class TestTemplate:
    def render(self, plugin, raw_config):
        plugin._add_locale(raw_config)
        plugin._add_timezone(raw_config)
        plugin._add_call_managers(raw_config)
        plugin._add_transport(raw_config)
        plugin._add_dtmf(raw_config)
        plugin._add_buttons(raw_config, '8851')
        raw_config['XX_xivo_phonebook_url'] = 'http://192.168.10.60/a?b=1&c=2'
        env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
        return env.get_template('base.tpl').render(raw_config)

    def test_render_is_valid_xml(self, plugin, raw_config):
        raw_config['sip_lines']['1']['auth_username'] = ''
        root = ET.fromstring(self.render(plugin, raw_config).encode('utf-8'))

        processnode = root.find(
            'devicePool/callManagerGroup/members/member/callManager'
        )
        assert processnode is not None
        assert processnode.findtext('processNodeName') == '192.168.10.60'
        assert processnode.findtext('ports/sipPort') == '5060'

        lines = root.findall('sipProfile/sipLines/line')
        assert [line.get('button') for line in lines] == ['1', '2', '3']
        line = lines[0]
        assert line.findtext('proxy') == 'USECALLMANAGER'
        assert line.findtext('authName') == 'abcdef12'
        assert line.findtext('authPassword') == 'secret&<>'
        assert line.findtext('displayName') == 'Niko & Co'
        assert line.findtext('messagesNumber') == '*98'
        assert lines[1].findtext('speedDialNumber') == '1002'
        assert lines[2].findtext('featureID') == '21'

        assert root.findtext('userLocale/name') == 'German_Germany'
        assert root.findtext('networkLocale') == 'Germany'
        assert root.findtext('directoryURL') == 'http://192.168.10.60/a?b=1&c=2'
        assert root.findtext('devicePool/dateTimeSetting/ntps/ntp/name') == (
            '192.168.10.1'
        )
