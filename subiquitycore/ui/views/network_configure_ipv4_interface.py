# Copyright 2015 Canonical, Ltd.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging
import ipaddress

import netifaces

from urwid import Text, Pile, ListBox, Columns

from subiquitycore.view import BaseView
from subiquitycore.ui.buttons import done_btn, menu_btn, cancel_btn
from subiquitycore.ui.utils import Color, Padding
from subiquitycore.ui.interactive import StringEditor


log = logging.getLogger('subiquitycore.network.network_configure_ipv4_interface')


class NetworkConfigureIPv4InterfaceView(BaseView):
    def __init__(self, model, controller, name):
        self.model = model
        self.controller = controller
        self.dev = self.model.get_netdev_by_name(name)
        self.is_gateway = False
        self.subnet_input = StringEditor(caption="")  # FIXME: ipaddr_editor
        self.address_input = StringEditor(caption="")  # FIXME: ipaddr_editor
        if self.dev.configured_ipv4_addresses:
            addr = ipaddress.ip_interface(self.dev.configured_ipv4_addresses[0])
            self.subnet_input.value = str(addr.network)
            self.address_input.value = str(addr.ip)
        self.gateway_input = StringEditor(caption="")  # FIXME: ipaddr_editor
        if self.dev.configured_gateway4:
            self.gateway_input.value = self.dev.configured_gateway4
        self.nameserver_input = StringEditor(caption="")  # FIXME: ipaddr_list_editor
        self.nameserver_input.value = ', '.join(self.dev.configured_nameservers)
        self.searchdomains_input = StringEditor(caption="")  # FIXME: ipaddr_list_editor
        self.searchdomains_input.value = ', '.join(self.dev.configured_searchdomains)
        self.error = Text("", align='center')
        self.set_as_default_gw_button = Pile(self._build_set_as_default_gw_button())
        body = [
            Padding.center_79(self._build_iface_inputs()),
            Padding.line_break(""),
            Padding.center_79(self.set_as_default_gw_button),
            Padding.line_break(""),
            Padding.center_90(Color.info_error(self.error)),
            Padding.line_break(""),
            Padding.fixed_10(self._build_buttons())
        ]
        super().__init__(ListBox(body))

    def _build_iface_inputs(self):
        col1 = [
            Columns(
                [
                    ("weight", 0.2, Text("Subnet")),
                    ("weight", 0.3,
                     Color.string_input(self.subnet_input,
                                        focus_map="string_input focus")),
                    ("weight", 0.5, Text("CIDR e.g. 192.168.9.0/24"))
                ], dividechars=2
            ),
            Columns(
                [
                    ("weight", 0.2, Text("Address")),
                    ("weight", 0.3,
                     Color.string_input(self.address_input,
                                        focus_map="string_input focus")),
                    ("weight", 0.5, Text(""))
                ], dividechars=2
            ),
            Columns(
                [
                    ("weight", 0.2, Text("Gateway")),
                    ("weight", 0.3,
                     Color.string_input(self.gateway_input,
                                        focus_map="string_input focus")),
                    ("weight", 0.5, Text(""))
                ], dividechars=2
            ),
            Columns(
                [
                    ("weight", 0.2, Text("Name servers:")),
                    ("weight", 0.3,
                     Color.string_input(self.nameserver_input,
                                        focus_map="string_input focus")),
                    ("weight", 0.5, Text("IP addresses, comma separated"))
                ], dividechars=2
            ),
            Columns(
                [
                    ("weight", 0.2, Text("Search domains:")),
                    ("weight", 0.3,
                     Color.string_input(self.searchdomains_input,
                                        focus_map="string_input focus")),
                    ("weight", 0.5, Text("Domains, comma separated"))
                ], dividechars=2
            ),
        ]
        return Pile(col1)

    def _build_set_as_default_gw_button(self):
        devs = self.model.get_all_netdevs()

        self.is_gateway = self.model.v4_gateway_dev == self.dev.name

        if not self.is_gateway and len(devs) > 1:
            btn = menu_btn(label="Set this as default gateway",
                           on_press=self.set_default_gateway)
        else:
            btn = Text("This will be your default gateway")

        return [btn]

    def set_default_gateway(self, button):
        if self.gateway_input.value:
            try:
                self.model.set_default_v4_gateway(self.dev.name,
                                                  self.gateway_input.value)
                self.is_gateway = True
                self.set_as_default_gw_button.contents = \
                    [ (obj, ('pack', None)) \
                           for obj in self._build_set_as_default_gw_button() ]
            except ValueError:
                # FIXME: set error message UX ala identity
                pass

    def _build_buttons(self):
        cancel = cancel_btn(on_press=self.cancel)
        done = done_btn(on_press=self.done)

        buttons = [
            Color.button(done, focus_map='button focus'),
            Color.button(cancel, focus_map='button focus')
        ]
        return Pile(buttons)

    def validate(self, result):
        if '/' not in result['network']:
            raise ValueError("Network should be in CIDR form (xx.xx.xx.xx/yy)")

        netmask = result['network'].split('/')[1]
        if int(netmask) > 32 or int(netmask) < 0:
            raise ValueError("CIDR netmask value should be between 0 and 32")
        for ns in result['nameservers']:
            try:
                ipaddress.ip_address(ns)
            except ValueError as v:
                raise ValueError("Nameserver " + str(v))

    def done(self, btn):
        searchdomains = []
        for sd in self.searchdomains_input.value.split(','):
            sd = sd.strip()
            if sd:
                searchdomains.append(sd.strip())
        nameservers = []
        for ns in self.nameserver_input.value.split(','):
            ns = ns.strip()
            if ns:
                nameservers.append(ns.strip())
        result = {
            'network': self.subnet_input.value,
            'address': self.address_input.value,
            'gateway': self.gateway_input.value,
            'nameservers': nameservers,
            'searchdomains': searchdomains,
        }
        try:
            self.validate(result)
            self.dev.remove_ipv4_networks()
            self.dev.add_network(netifaces.AF_INET, result)
        except ValueError as e:
            error = 'Failed to manually configure interface: {}'.format(e)
            log.exception(error)
            self.error.set_text(str(e))
            #self.iface.configure_from_info()
            # FIXME: set error message in UX ala identity
            return

        # return
        self.controller.prev_view()

    def cancel(self, button):
        self.model.default_gateway = None
        self.controller.prev_view()
