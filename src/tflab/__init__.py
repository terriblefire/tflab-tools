# Copyright (C) 2016-2026 S.J. Leary
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <https://www.gnu.org/licenses/>.

__version__ = "0.2.0rc1"

from .hp1660 import (HP1660, SocketTransport, VisaTransport,
                     FormatConfig, TriggerConfig, TriggerTerm, TriggerLevel,
                     Acquisition, Label)

__all__ = ["HP1660", "SocketTransport", "VisaTransport",
           "FormatConfig", "TriggerConfig", "TriggerTerm", "TriggerLevel",
           "Acquisition", "Label", "__version__"]
