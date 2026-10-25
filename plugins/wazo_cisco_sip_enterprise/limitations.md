# Limitations

Tested with a Cisco CP-8851 running enterprise firmware sip88xx.12-7-1-0001-393
against Wazo 26.10.

## Working

* Provisioning over TFTP (DHCP option 66 or 150), `SEP<MAC>.cnf.xml`
* Registration, incoming and outgoing calls, audio in both directions
* Time zone, date and NTP

## Known issues

* A phone previously registered to a CUCM keeps that cluster's ITL file and only
  requests signed files (`*.cnf.xml.sgn`). It must be factory reset first (see
  `install.md`).
* German (and other) user locales require the Cisco locale installer to be
  copied to the TFTP directory; without it the phone falls back to English.
