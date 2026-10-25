# Limitations

Tested with a Cisco CP-8851 running enterprise firmware sip88xx.12-7-1-0001-393
against Wazo 26.10.

## Working

* Provisioning over TFTP (DHCP option 66 or 150), `SEP<MAC>.cnf.xml`
* Registration, incoming and outgoing calls, audio in both directions
* G.722 wideband audio (`advertiseG722Codec`); Asterisk puts the codec of the
  other call leg first in its offer, so both legs must support G.722 (e.g. it
  is disabled by default in Linphone for iOS)
* Time zone, date and NTP
* Key expansion module (CP-BEKEM), BLF and speed dial keys, directory (Contacts
  key), voicemail

## Known issues

* Resynchronization is not reliable. The phones answer the usual `check-sync`
  NOTIFY with 200 but ignore it. The plugin sends a Cisco `service-control`
  NOTIFY (`action=check-version`, empty `RegisterCallId`, `ConfigVersionStamp`
  set to the `<versionStamp>` of the generated configuration). sip88xx 12.7.1
  downloaded its configuration on such a NOTIFY twice, then stopped reacting to
  it (200, no download). `restart` and `apply-config` are rejected with 400.
  Restart the phone (e.g. PoE power cycle) to apply configuration changes.

* A phone previously registered to a CUCM keeps that cluster's ITL file and only
  requests signed files (`*.cnf.xml.sgn`). It must be factory reset first (see
  `install.md`).
* German (and other) user locales require the Cisco locale installer to be
  copied to the TFTP directory; without it the phone falls back to English.
