# Installation

This plugin is for Cisco 78xx and 88xx phones running the **enterprise** SIP
firmware (loads named `sip78xx.*` / `sip88xx.*`, as shipped for CUCM). Phones
running the multiplatform firmware (`*MPP*` loads) must use the
`wazo-cisco-sip` plugin instead.

## Preparing a phone coming from a CUCM cluster

A phone that was registered to a CUCM keeps the ITL (and possibly CTL) file of
that cluster and will refuse unsigned configuration files. Factory reset it
first:

1. Unplug the phone.
2. Hold `#` while plugging it back in.
3. When the line keys light up, release `#` and type `123456789*0#`.

## DHCP

The phone looks for its TFTP server in DHCP option 150 (or option 66). Point it
to the Wazo server:

    option 150 = <IP of the Wazo server>

## Firmware and locales

Enterprise firmwares and locale installers can only be downloaded from
software.cisco.com. Copy the content of the firmware zip
(`cmterm-88xx.<version>.zip`, ...) into the `var/tftpboot` directory of the
plugin, i.e. `/var/lib/wazo-provd/plugins/wazo-cisco-sip-enterprise-14/var/tftpboot`,
then set the load name (without extension, e.g. `sip88xx.14-3-1-0001-xxx`) in a
custom template:

    # /var/lib/wazo-provd/plugins/wazo-cisco-sip-enterprise-14/var/templates/8851.tpl
    {% extends 'base.tpl' -%}
    {% block loadInformation %}sip88xx.14-3-1-0001-xxx{% endblock -%}

When `loadInformation` is empty, the phone keeps its current firmware.

## Dial plan

`var/tftpboot/dialplan.xml` dials 4 digit extensions starting with 1
immediately. Adapt it to your extension ranges.
