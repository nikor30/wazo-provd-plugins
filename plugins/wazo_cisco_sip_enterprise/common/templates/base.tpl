<?xml version="1.0" encoding="UTF-8"?>
<device>
 <fullConfig>true</fullConfig>
 <deviceProtocol>SIP</deviceProtocol>
 <ipAddressMode>0</ipAddressMode>
 <allowAutoConfig>true</allowAutoConfig>
 <devicePool>
  <revertPriority>0</revertPriority>
  <name>Wazo</name>
  <dateTimeSetting>
   <name>Wazo</name>
   <dateTemplate>D.M.YA</dateTemplate>
   <timeZone>{{ XX_timezone }}</timeZone>
   <ntps>
    {% if ntp_enabled -%}
    <ntp>
     <name>{{ ntp_ip }}</name>
     <ntpMode>Unicast</ntpMode>
    </ntp>
    {% endif -%}
   </ntps>
  </dateTimeSetting>
  <callManagerGroup>
   <name>Wazo</name>
   <tftpDefault>true</tftpDefault>
   <members>
    {% for call_manager in XX_call_managers -%}
    <member priority="{{ loop.index0 }}">
     <callManager>
      <name>wazo{{ loop.index0 }}</name>
      <ports>
       <ethernetPhonePort>2000</ethernetPhonePort>
       <sipPort>{{ call_manager['port'] }}</sipPort>
       <securedSipPort>5061</securedSipPort>
      </ports>
      <processNodeName>{{ call_manager['ip'] }}</processNodeName>
     </callManager>
    </member>
    {% endfor -%}
   </members>
  </callManagerGroup>
  <srstInfo>
   <name>Disable</name>
   <srstOption>Disable</srstOption>
   <userModifiable>false</userModifiable>
   <isSecure>false</isSecure>
  </srstInfo>
 </devicePool>
 <sipProfile>
  <sipProxies>
   <registerWithProxy>true</registerWithProxy>
  </sipProxies>
  <sipCallFeatures>
   <cnfJoinEnabled>true</cnfJoinEnabled>
   <rfc2543Hold>false</rfc2543Hold>
   <callHoldRingback>2</callHoldRingback>
   <localCfwdEnable>true</localCfwdEnable>
   <semiAttendedTransfer>true</semiAttendedTransfer>
   <anonymousCallBlock>2</anonymousCallBlock>
   <callerIdBlocking>2</callerIdBlocking>
   <dndControl>0</dndControl>
   <remoteCcEnable>false</remoteCcEnable>
   <retainForwardInformation>false</retainForwardInformation>
  </sipCallFeatures>
  <sipStack>
   <sipInviteRetx>6</sipInviteRetx>
   <sipRetx>10</sipRetx>
   <timerInviteExpires>180</timerInviteExpires>
   <timerRegisterExpires>3600</timerRegisterExpires>
   <timerRegisterDelta>5</timerRegisterDelta>
   <timerKeepAliveExpires>120</timerKeepAliveExpires>
   <timerSubscribeExpires>120</timerSubscribeExpires>
   <timerSubscribeDelta>5</timerSubscribeDelta>
   <timerT1>500</timerT1>
   <timerT2>4000</timerT2>
   <maxRedirects>70</maxRedirects>
   <remotePartyID>true</remotePartyID>
   <userInfo>None</userInfo>
  </sipStack>
  <autoAnswerTimer>1</autoAnswerTimer>
  <autoAnswerAltBehavior>false</autoAnswerAltBehavior>
  <autoAnswerOverride>true</autoAnswerOverride>
  <transferOnhookEnabled>true</transferOnhookEnabled>
  <enableVad>false</enableVad>
  <preferredCodec>none</preferredCodec>
  <dtmfAvtPayload>101</dtmfAvtPayload>
  <dtmfDbLevel>3</dtmfDbLevel>
  <dtmfOutofBand>{{ XX_dtmf_out_of_band }}</dtmfOutofBand>
  <kpml>0</kpml>
  <phoneLabel>{% block phone_label %}Wazo{% endblock %}</phoneLabel>
  <stutterMsgWaiting>1</stutterMsgWaiting>
  <callStats>false</callStats>
  <offhookToFirstDigitTimer>15000</offhookToFirstDigitTimer>
  <silentPeriodBetweenCallWaitingBursts>10</silentPeriodBetweenCallWaitingBursts>
  <disableLocalSpeedDialConfig>false</disableLocalSpeedDialConfig>
  <startMediaPort>16384</startMediaPort>
  <stopMediaPort>32766</stopMediaPort>
  <sipLines>
   {% for button_no, button in XX_buttons -%}
   {% if button['feature_id'] == 9 -%}
   {% set line = button['line'] -%}
   <line button="{{ button_no }}" lineIndex="{{ button['line_index'] }}">
    <featureID>9</featureID>
    <featureLabel>{% block line_label scoped %}{{ button['label'] }}{% endblock %}</featureLabel>
    <proxy>USECALLMANAGER</proxy>
    <port>{{ XX_call_managers[0]['port'] }}</port>
    <name>{{ line['username']|e }}</name>
    <displayName>{{ line['display_name']|e }}</displayName>
    <autoAnswer>
     <autoAnswerEnabled>2</autoAnswerEnabled>
    </autoAnswer>
    <callWaiting>3</callWaiting>
    <authName>{{ (line['auth_username'] or line['username'])|e }}</authName>
    <authPassword>{{ line['password']|e }}</authPassword>
    <sharedLine>false</sharedLine>
    <messageWaitingLampPolicy>3</messageWaitingLampPolicy>
    <messageWaitingAMWI>1</messageWaitingAMWI>
    <messagesNumber>{{ line['voicemail']|d(exten_voicemail)|d('')|e }}</messagesNumber>
    <ringSettingIdle>4</ringSettingIdle>
    <ringSettingActive>5</ringSettingActive>
    <contact>{{ line['username']|e }}</contact>
    <maxNumCalls>4</maxNumCalls>
    <busyTrigger>2</busyTrigger>
   </line>
   {% else -%}
   <line button="{{ button_no }}">
    <featureID>{{ button['feature_id'] }}</featureID>
    <featureLabel>{{ button['label'] }}</featureLabel>
    <speedDialNumber>{{ button['number'] }}</speedDialNumber>
   </line>
   {% endif -%}
   {% endfor -%}
   {% block extra_lines %}{% endblock -%}
  </sipLines>
  <voipControlPort>5060</voipControlPort>
  <dscpForAudio>184</dscpForAudio>
  <ringSettingBusyStationPolicy>0</ringSettingBusyStationPolicy>
  <dialTemplate>dialplan.xml</dialTemplate>
 </sipProfile>
 <commonProfile>
  <phonePassword></phonePassword>
  <backgroundImageAccess>true</backgroundImageAccess>
  <callLogBlfEnabled>2</callLogBlfEnabled>
 </commonProfile>
 <versionStamp>XX_VERSION_STAMP</versionStamp>
 <loadInformation>{% block loadInformation %}{% endblock %}</loadInformation>
 <vendorConfig>
  <webAccess>0</webAccess>
  <settingsAccess>1</settingsAccess>
  <garp>1</garp>
  <pcPort>0</pcPort>
  <spanToPCPort>1</spanToPCPort>
  <loggingDisplay>1</loggingDisplay>
  <g722CodecSupport>2</g722CodecSupport>
  <enableGroupListen>1</enableGroupListen>
 </vendorConfig>
 {% if XX_addons -%}
 <addOnModules>
  {% for addon in XX_addons -%}
  <addOnModule idx="{{ addon['idx'] }}">
   <deviceType>{{ addon['type'] }}</deviceType>
   <deviceLine>{{ addon['lines'] }}</deviceLine>
   <loadInformation></loadInformation>
  </addOnModule>
  {% endfor -%}
 </addOnModules>
 {% endif -%}
 {% if XX_locale -%}
 <userLocale>
  <name>{{ XX_locale[0] }}</name>
  <langCode>{{ XX_locale[1] }}</langCode>
 </userLocale>
 <networkLocale>{{ XX_locale[2] }}</networkLocale>
 {% endif -%}
 <deviceSecurityMode>1</deviceSecurityMode>
 <transportLayerProtocol>{{ XX_transport }}</transportLayerProtocol>
 <dndCallAlert>5</dndCallAlert>
 <idleTimeout>{% block idle_timeout %}0{% endblock %}</idleTimeout>
 <authenticationURL>{% block authentication_url %}{% endblock %}</authenticationURL>
 <directoryURL>{{ XX_xivo_phonebook_url|e }}</directoryURL>
 <idleURL>{% block idle_url %}{% endblock %}</idleURL>
 <informationURL>{% block information_url %}{% endblock %}</informationURL>
 <messagesURL></messagesURL>
 <proxyServerURL></proxyServerURL>
 <servicesURL>{% block services_url %}{% endblock %}</servicesURL>
 <encrConfig>false</encrConfig>
 <phoneServices useHTTPS="false">
  <provisioning>2</provisioning>
  <phoneService type="1" category="0">
   <name>Missed Calls</name>
   <url>Application:Cisco/MissedCalls</url>
   <vendor></vendor>
   <version></version>
  </phoneService>
  <phoneService type="1" category="0">
   <name>Received Calls</name>
   <url>Application:Cisco/ReceivedCalls</url>
   <vendor></vendor>
   <version></version>
  </phoneService>
  <phoneService type="1" category="0">
   <name>Placed Calls</name>
   <url>Application:Cisco/PlacedCalls</url>
   <vendor></vendor>
   <version></version>
  </phoneService>
  {% if XX_xivo_phonebook_url -%}
  <phoneService type="1" category="0">
   <name>{{ XX_directory_name }}</name>
   <url>{{ XX_xivo_phonebook_url|e }}</url>
   <vendor></vendor>
   <version></version>
  </phoneService>
  {% endif -%}
  <phoneService type="2" category="0">
   <name>Voicemail</name>
   <url>Application:Cisco/Voicemail</url>
   <vendor></vendor>
   <version></version>
  </phoneService>
  {% block phone_services %}{% endblock -%}
 </phoneServices>
</device>
