# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import TypedDict

    from ..common.common import (  # noqa: F401
        BaseCiscoPgAssociator,
        BaseCiscoSipEnterprisePlugin,
    )

    class CommonGlobalsDict(TypedDict):
        BaseCiscoSipEnterprisePlugin: type[BaseCiscoSipEnterprisePlugin]
        BaseCiscoPgAssociator: type[BaseCiscoPgAssociator]


common: CommonGlobalsDict = {}  # type: ignore[typeddict-item]
execfile_('common.py', common)  # type: ignore[name-defined]

MODELS = [
    '7811',
    '7821',
    '7841',
    '7861',
    '8811',
    '8841',
    '8845',
    '8851',
    '8861',
    '8865',
]


class CiscoSipEnterprisePlugin(
    common['BaseCiscoSipEnterprisePlugin']  # type: ignore[valid-type,misc]
):
    IS_PLUGIN = True

    pg_associator = common['BaseCiscoPgAssociator'](MODELS)
